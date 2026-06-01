import re
from pathlib import Path

import pdfplumber


BASE_DIR = Path("data/fda_ai/devices")
RAW_DIR = BASE_DIR / "raw"
EXTRACTED_DIR = BASE_DIR / "extracted"
CLEANED_DIR = BASE_DIR / "cleaned"


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


def main():
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    for txt_file in EXTRACTED_DIR.glob("*.txt"):
        txt_file.unlink()
    for txt_file in CLEANED_DIR.glob("*.txt"):
        txt_file.unlink()

    for pdf_file in sorted(RAW_DIR.glob("*.pdf")):
        print(f"Extracting device submission: {pdf_file.name}")
        extracted_text = extract_text_from_pdf(pdf_file)
        extracted_path = EXTRACTED_DIR / f"{pdf_file.stem}.txt"
        extracted_path.write_text(extracted_text, encoding="utf-8")

        cleaned_text = clean_text(extracted_text)
        cleaned_path = CLEANED_DIR / f"{pdf_file.stem}.txt"
        cleaned_path.write_text(cleaned_text, encoding="utf-8")

    print("Completed device submission extraction and cleaning")


if __name__ == "__main__":
    main()
