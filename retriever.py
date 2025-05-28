from sentence_transformers import SentenceTransformer, util
import pandas as pd
import os

model = SentenceTransformer("paraphrase-MiniLM-L3-v2")  # Light + fast

def retrieve_similar_human_edit(new_text, csv_path="tone_training_log.csv", top_k=1):
    if not os.path.exists(csv_path):
        return None, None

    df = pd.read_csv(csv_path, names=["text", "image_url", "tone", "ai_message", "human_message"])
    texts = df["text"].fillna("").tolist()
    human_messages = df["human_message"].fillna("").tolist()

    if not texts:
        return None, None

    query_embedding = model.encode(new_text, convert_to_tensor=True)
    corpus_embeddings = model.encode(texts, convert_to_tensor=True)

    hits = util.semantic_search(query_embedding, corpus_embeddings, top_k=top_k)[0]

    if hits:
        index = hits[0]["corpus_id"]
        return texts[index], human_messages[index]
    return None, None
