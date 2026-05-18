from pathlib import Path
from nltk.tokenize.punkt import PunktSentenceTokenizer, PunktParameters
import nltk

# Ensure punkt is downloaded
nltk.download('punkt')

# Paths
CLEANED_DIR = Path("data/cleaned")
CHUNKED_DIR = Path("data/chunked")
CHUNKED_DIR.mkdir(parents=True, exist_ok=True)

# Load default English sentence tokenizer
punkt_param = PunktParameters()
tokenizer = PunktSentenceTokenizer(punkt_param)

# Function to chunk text
def chunk_text(text, max_chars=1000):
    sentences = tokenizer.tokenize(text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) < max_chars:
            current_chunk += " " + sentence
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

# Process each cleaned text file
for txt_file in CLEANED_DIR.glob("*.txt"):
    print(f"Chunking: {txt_file.name}")
    text = txt_file.read_text(encoding="utf-8")
    chunks = chunk_text(text)

    # Save chunks as individual files
    for i, chunk in enumerate(chunks):
        chunk_file = CHUNKED_DIR / f"{txt_file.stem}_chunk{i+1}.txt"
        chunk_file.write_text(chunk, encoding="utf-8")

print("✅ Chunking complete.")
