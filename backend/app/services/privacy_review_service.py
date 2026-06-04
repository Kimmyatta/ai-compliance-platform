from groq import Groq

from backend.app.core.config import require_groq_api_key


def _get_client():
    return Groq(api_key=require_groq_api_key())


def review_uploaded_document(filename, document_text):
    from document_review import parse_review_result, review_document

    raw_results = review_document(document_text, _get_client())
    return {
        "filename": filename,
        "reviews": [
            {
                "regulation": regulation,
                "parsed": parse_review_result(review_text),
                "review": review_text,
            }
            for regulation, review_text in raw_results.items()
        ],
    }
