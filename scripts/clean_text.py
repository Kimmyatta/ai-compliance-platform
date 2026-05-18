from pathlib import Path
import re

# Paths
EXTRACTED_DIR = Path("data/extracted")
CLEANED_DIR = Path("data/cleaned")

CLEANED_DIR.mkdir(parents=True, exist_ok=True)

# Function to clean text
def clean_text(text):
    # Remove extra whitespace and line breaks
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing spaces
    text = text.strip()
    return text

# Process each extracted text file
for txt_file in EXTRACTED_DIR.glob("*.txt"):
    print(f"Cleaning: {txt_file.name}")
    text = txt_file.read_text(encoding="utf-8")
    cleaned = clean_text(text)

    output_file = CLEANED_DIR / txt_file.name
    output_file.write_text(cleaned, encoding="utf-8")

print("✅ Cleaning complete.")
