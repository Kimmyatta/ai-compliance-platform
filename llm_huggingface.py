from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch


class HuggingFaceLLM:

    def __init__(self):

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        model_name = "google/flan-t5-base"

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(self.device)


    def generate(self, context, question):

        prompt = f"""
Answer the question using ONLY the context below.
If the answer is not contained in the context, say "I don't know."

Context:
{context}

Question: {question}
Answer:
"""

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=512
        ).to(self.device)

        outputs = self.model.generate(
            **inputs,
            max_new_tokens=150,
            do_sample=False
        )

        answer = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        if "Answer:" in answer:
            answer = answer.split("Answer:")[-1].strip()

        return answer