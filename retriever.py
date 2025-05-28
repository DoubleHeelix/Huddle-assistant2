import os
import pandas as pd
from sentence_transformers import SentenceTransformer, util

# ✅ Load model inside a function to avoid Streamlit file-watcher issues
def get_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

def retrieve_similar_human_edit(new_text, csv_path="tone_training_log.csv", top_k=1):
    if not os.path.exists(csv_path):
        return None, None

    df = pd.read_csv(csv_path, names=["text", "image_url", "tone", "ai_message", "human_message"])
    texts = df["text"].fillna("").tolist()
    human_messages = df["human_message"].fillna("").tolist()

    if not texts:
        return None, None

    model = get_model()
    query_embedding = model.encode(new_text, convert_to_tensor=True)
    corpus_embeddings = model.encode(texts, convert_to_tensor=True)

    hits = util.semantic_search(query_embedding, corpus_embeddings, top_k=top_k)[0]

    if hits:
        index = hits[0]["corpus_id"]
        return texts[index], human_messages[index]

    return None, None
