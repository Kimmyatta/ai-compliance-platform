from io import BytesIO

from fastapi import UploadFile


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _get_extension(filename):
    lower_name = (filename or "").lower()
    for extension in SUPPORTED_EXTENSIONS:
        if lower_name.endswith(extension):
            return extension
    return ""


def _extract_pdf_text(content):
    import fitz

    text = []
    with fitz.open(stream=content, filetype="pdf") as pdf:
        for page in pdf:
            page_text = page.get_text()
            if page_text:
                text.append(page_text)
    return "\n".join(text).strip()


def _extract_docx_text(content):
    from docx import Document

    document = Document(BytesIO(content))
    return "\n".join(
        paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()
    ).strip()


def _extract_txt_text(content):
    return content.decode("utf-8", errors="replace").strip()


async def extract_text_from_upload(file: UploadFile):
    filename = file.filename or "uploaded_document"
    extension = _get_extension(filename)
    if not extension:
        raise ValueError("Unsupported file type. Upload a PDF, DOCX, or TXT file.")

    content = await file.read()
    if not content:
        raise ValueError("Uploaded file is empty.")

    if extension == ".pdf":
        text = _extract_pdf_text(content)
    elif extension == ".docx":
        text = _extract_docx_text(content)
    else:
        text = _extract_txt_text(content)

    if not text:
        raise ValueError("No readable text could be extracted from the uploaded file.")

    return filename, text
