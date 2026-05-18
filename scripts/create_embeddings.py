import os
import json
from sentence_transformers import SentenceTransformer

CHUNK_DIR = "data/chunked"
OUTPUT_FILE = "data/embeddings/embeddings.json"

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

data = []

for filename in sorted(os.listdir(CHUNK_DIR)):
    if not filename.endswith(".txt"):
        continue

    path = os.path.join(CHUNK_DIR, filename)

    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    embedding = model.encode(text, normalize_embeddings=True).tolist()

    data.append({
        "filename": filename,
        "text": text,
        "embedding": embedding
    })

os.makedirs("data/embeddings", exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f)

print("✅ Embeddings created")
