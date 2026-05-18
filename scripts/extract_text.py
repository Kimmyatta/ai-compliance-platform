import pdfplumber
from pathlib import Path

RAW_DIR = Path("data/raw")
EXTRACTED_DIR = Path("data/extracted")

EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

for pdf_file in RAW_DIR.glob("*.pdf"):
    print(f"Extracting: {pdf_file.name}")
    text = extract_text_from_pdf(pdf_file)

    output_file = EXTRACTED_DIR / f"{pdf_file.stem}.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(text)

print("✅ Extraction complete.")
