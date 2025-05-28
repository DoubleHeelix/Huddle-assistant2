import openai
import pandas as pd
import numpy as np
import os

openai.api_key = os.getenv("OPENAI_API_KEY")  # Ensure this is set in your environment

def get_embedding(text):
    response = openai.Embedding.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']

def cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def retrieve_similar_human_edit(new_text, csv_path="tone_training_log.csv", top_k=1):
    if not os.path.exists(csv_path):
        return None, None

    df = pd.read_csv(csv_path, names=["text", "image_url", "tone", "ai_message", "human_message"])
    df["text"] = df["text"].fillna("")
    df["human_message"] = df["human_message"].fillna("")

    if df.empty:
        return None, None

    query_embedding = get_embedding(new_text)
    corpus_embeddings = df["text"].apply(get_embedding).tolist()

    similarities = [cosine_similarity(query_embedding, emb) for emb in corpus_embeddings]
    top_idx = int(np.argmax(similarities))

    return df.iloc[top_idx]["text"], df.iloc[top_idx]["human_message"]
