import faiss
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import os
from groq import Groq
from prompt import build_prompt

client=Groq(api_key=os.getenv("GROQ_API_KEY"))

embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")


index = faiss.read_index("data/faiss_index/index.faiss")

with open("data/faiss_index/metadata.json", "r") as f:
    metadata = json.load(f)

def get_risk_score(answer):
    answer_lower = answer.lower()

    if "not compliant" in answer_lower:
        return 25, "HIGH"
    elif "partially compliant" in answer_lower:
        return 60, "MEDIUM"
    elif "compliant" in answer_lower:
        return 90, "LOW"
    else:
        return 50, "UNKNOWN"
    

def ask(question, k=5):
    query_vec = embedder.encode(
        [question],
        normalize_embeddings=True
    ).astype("float32")

    _, indices = index.search(query_vec, k)

    print("\nRetrieved chunks:")
    for i in indices[0]:
        print(metadata[str(i)]["source"])

    context = "\n\n".join(
        metadata[str(i)]["text"][:400]
        for i in indices[0]
    )
    
     # UPGRADED PROMPT (COMPLIANCE-AWARE)

    prompt = build_prompt(context, question)

    # Call Groq API
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a legal compliance assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
    )

    # ✅ GET ANSWER
    answer = response.choices[0].message.content.strip()

    # ✅ APPLY RISK SCORING
    score, risk = get_risk_score(answer)

    # ✅ FORMAT FINAL OUTPUT
    final_output = f"""
    {answer}

    Risk Score: {score}%
    Risk Level: {risk}
    """

    # ✅ LOGGING (ADD THIS BLOCK)
    log = {
        "question": question,
        "retrieved_chunks": [metadata[str(i)]["source"] for i in indices[0]],
        "answer": answer,
        "risk_score": score,
        "risk_level": risk
    }

    with open("logs.json", "a") as f:
     json.dump(log, f)
     f.write("\n")

    # ✅ RETURN AFTER LOGGING
    return final_output
    
    
print("\n🤖 Compliance Q&A Bot (type 'exit' to quit)\n")

while True:
    q = input("Enter your question: ")
    if q.lower() == "exit":
        break
    print(ask(q), "\n")