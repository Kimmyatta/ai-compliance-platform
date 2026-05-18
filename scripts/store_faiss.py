import json
import os

import faiss
import numpy as np

EMBEDDINGS_FILE = "data/embeddings/embeddings.json"
INDEX_DIR = "data/faiss_index"

with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

vectors = np.array([item["embedding"] for item in data]).astype("float32")

index = faiss.IndexFlatL2(vectors.shape[1])
index.add(vectors)

os.makedirs(INDEX_DIR, exist_ok=True)
faiss.write_index(index, f"{INDEX_DIR}/index.faiss")

metadata = {
    str(i): {
        "text": item["text"],
        "source": item["filename"],
    }
    for i, item in enumerate(data)
}

with open(f"{INDEX_DIR}/metadata.json", "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)

print("FAISS index rebuilt with text metadata")
