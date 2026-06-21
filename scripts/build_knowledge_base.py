import argparse
import json
import re
from pathlib import Path

import faiss
import numpy as np
import pdfplumber
from nltk.tokenize.punkt import PunktParameters, PunktSentenceTokenizer
from sentence_transformers import SentenceTransformer


DATASETS = {
    "privacy": Path("data/privacy"),
    "fda_guidance": Path("data/fda_ai/guidance"),
    "afrisafe_frameworks": Path("data/afrisafebench/frameworks"),
}


def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text, tokenizer, max_chars=1000):
    sentences = tokenizer.tokenize(text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) < max_chars:
            current_chunk += " " + sentence
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def reset_txt_outputs(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for file_path in directory.glob("*.txt"):
        file_path.unlink()


def embed_chunks(chunked_dir, chunk_files, model):
    embedding_data = []

    for path in sorted(chunk_files):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue

        print(f"Embedding: {path.name}")
        embedding = model.encode(text, normalize_embeddings=True).tolist()
        embedding_data.append(
            {
                "filename": path.name,
                "text": text,
                "embedding": embedding,
            }
        )

    return embedding_data


def write_index(embedding_data, embeddings_dir, faiss_dir, dataset_name):
    embeddings_file = embeddings_dir / "embeddings.json"
    embeddings_file.write_text(json.dumps(embedding_data), encoding="utf-8")

    if not embedding_data:
        raise RuntimeError(f"No embeddings were created for {dataset_name}")

    vectors = np.array([item["embedding"] for item in embedding_data]).astype("float32")
    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, str(faiss_dir / "index.faiss"))

    metadata = {
        str(i): {
            "text": item["text"],
            "source": item["filename"],
        }
        for i, item in enumerate(embedding_data)
    }
    (faiss_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def build_dataset(dataset_name, incremental=False, filenames=None):
    base_dir = DATASETS[dataset_name]
    raw_dir = base_dir / "raw"
    extracted_dir = base_dir / "extracted"
    cleaned_dir = base_dir / "cleaned"
    chunked_dir = base_dir / "chunked"
    embeddings_dir = base_dir / "embeddings"
    faiss_dir = base_dir / "faiss_index"

    for directory in [raw_dir, extracted_dir, cleaned_dir, chunked_dir, embeddings_dir, faiss_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    if incremental:
        if filenames:
            pdf_files = [raw_dir / filename for filename in filenames]
        else:
            pdf_files = [
                pdf_file
                for pdf_file in sorted(raw_dir.glob("*.pdf"))
                if not (extracted_dir / f"{pdf_file.stem}.txt").exists()
            ]
        missing_files = [path.name for path in pdf_files if not path.exists()]
        if missing_files:
            raise FileNotFoundError(f"Missing raw PDF files: {', '.join(missing_files)}")
        if not pdf_files:
            print(f"No new PDFs found for incremental update: {dataset_name}")
            return
        print(f"Incrementally updating knowledge base: {dataset_name}")
    else:
        reset_txt_outputs(extracted_dir)
        reset_txt_outputs(cleaned_dir)
        reset_txt_outputs(chunked_dir)
        pdf_files = sorted(raw_dir.glob("*.pdf"))
        print(f"Building knowledge base: {dataset_name}")

    for pdf_file in pdf_files:
        print(f"Extracting: {pdf_file.name}")
        text = extract_text_from_pdf(pdf_file)
        (extracted_dir / f"{pdf_file.stem}.txt").write_text(text, encoding="utf-8")

    extracted_files = [extracted_dir / f"{pdf_file.stem}.txt" for pdf_file in pdf_files]
    for txt_file in extracted_files:
        print(f"Cleaning: {txt_file.name}")
        text = txt_file.read_text(encoding="utf-8")
        (cleaned_dir / txt_file.name).write_text(clean_text(text), encoding="utf-8")

    tokenizer = PunktSentenceTokenizer(PunktParameters())

    cleaned_files = [cleaned_dir / f"{pdf_file.stem}.txt" for pdf_file in pdf_files]
    for txt_file in cleaned_files:
        print(f"Chunking: {txt_file.name}")
        for old_chunk in chunked_dir.glob(f"{txt_file.stem}_chunk*.txt"):
            old_chunk.unlink()
        text = txt_file.read_text(encoding="utf-8")
        chunks = chunk_text(text, tokenizer)
        for index, chunk in enumerate(chunks, start=1):
            chunk_file = chunked_dir / f"{txt_file.stem}_chunk{index}.txt"
            chunk_file.write_text(chunk, encoding="utf-8")

    model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    if incremental:
        embeddings_file = embeddings_dir / "embeddings.json"
        existing_data = json.loads(embeddings_file.read_text(encoding="utf-8"))
        updated_stems = {pdf_file.stem for pdf_file in pdf_files}
        embedding_data = [
            item
            for item in existing_data
            if not any(item["filename"].startswith(f"{stem}_chunk") for stem in updated_stems)
        ]
        new_chunk_files = [
            path
            for stem in updated_stems
            for path in chunked_dir.glob(f"{stem}_chunk*.txt")
        ]
        embedding_data.extend(embed_chunks(chunked_dir, new_chunk_files, model))
        embedding_data.sort(key=lambda item: item["filename"])
    else:
        embedding_data = embed_chunks(chunked_dir, chunked_dir.glob("*.txt"), model)

    write_index(embedding_data, embeddings_dir, faiss_dir, dataset_name)

    print(f"Completed: {dataset_name}")


def main():
    parser = argparse.ArgumentParser(description="Build a dataset-specific regulatory knowledge base.")
    parser.add_argument("dataset", choices=sorted(DATASETS.keys()))
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Process only selected or newly added PDFs and preserve existing embeddings.",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        help="Raw PDF filenames to process during an incremental update.",
    )
    args = parser.parse_args()
    build_dataset(args.dataset, incremental=args.incremental, filenames=args.files)


if __name__ == "__main__":
    main()
