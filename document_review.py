import faiss
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from groq import Groq
import os
from prompt import build_document_review_prompt

embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
index = faiss.read_index("data/faiss_index/index.faiss")

with open("data/faiss_index/metadata.json", "r") as f:
    metadata = json.load(f)

REGULATIONS = ["CCPA", "HIPAA", "HITECH"]

def get_regulation_context(regulation, k=5):
    query_vec = embedder.encode(
        [regulation],
        normalize_embeddings=True
    ).astype("float32")

    _, indices = index.search(query_vec, k)

    context = "\n\n".join(
        metadata[str(i)]["text"][:400]
        for i in indices[0]
    )
    return context

def review_document(document_text, client):
    results = {}

    for regulation in REGULATIONS:
        context = get_regulation_context(regulation)
        prompt = build_document_review_prompt(context, document_text, regulation)

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a legal compliance expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            results[regulation] = response.choices[0].message.content.strip()
        except Exception as e:
            results[regulation] = f"Error reviewing against {regulation}: {str(e)}"

    return results

def parse_review_result(result_text):
    sections = {
        "compliance_summary": "",
        "compliant_sections": "",
        "violations": "",
        "missing_requirements": "",
        "risk_level": "",
        "recommendations": ""
    }

    mappings = {
        "Compliance Summary:": "compliance_summary",
        "Compliant Sections:": "compliant_sections",
        "Violations Found:": "violations",
        "Missing Requirements:": "missing_requirements",
        "Risk Level:": "risk_level",
        "Recommendations:": "recommendations"
    }

    current_key = None
    for line in result_text.split("\n"):
        line = line.strip()
        matched = False
        for label, key in mappings.items():
            if line.startswith(label):
                current_key = key
                sections[key] = line[len(label):].strip()
                matched = True
                break
        if not matched and current_key and line and line != "---":
            sections[current_key] += "\n" + line

    return sections