import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def embed_batch(texts, model="text-embedding-3-small"):
    response = openai.embeddings.create(
        model=model,
        input=texts
    )
    return [r.embedding for r in response.data]

def embed_single(text, model="text-embedding-3-small"):
    return embed_batch([text])[0]
