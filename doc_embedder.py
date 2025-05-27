from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from vectorizer import embed_batch
import os
import fitz  # PyMuPDF
from dotenv import load_dotenv
from uuid import uuid4
import concurrent.futures

load_dotenv()

pdf_dir = "public"
collection_name = "docs_memory"
VECTOR_SIZE = 1536  # OpenAI embeddings

def extract_text_from_pdf(path):
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def chunk_text(text, max_chars=1000):
    sentences = text.split(". ")
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= max_chars:
            current += sentence + ". "
        else:
            chunks.append(current.strip())
            current = sentence + ". "
    if current:
        chunks.append(current.strip())
    return chunks

def process_file(path, filename, VECTOR_SIZE):
    try:
        raw_text = extract_text_from_pdf(path)
        chunks = chunk_text(raw_text)
        if not chunks:
            print(f"[WARNING] No chunks found in {filename}")
            return []
        vectors = embed_batch(chunks)  # List of 1536-dim vectors
        points = []
        for chunk, vector in zip(chunks, vectors):
            points.append(
                PointStruct(
                    id=str(uuid4()),
                    vector=vector,
                    payload={
                        "document": chunk,
                        "source": filename
                    }
                )
            )
        return points
    except Exception as e:
        print(f"[ERROR] Failed to process {filename}: {e}")
        return []

def embed_documents_parallel(pdf_dir, collection_name, VECTOR_SIZE):
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )
    # Ensure the collection exists
    try:
        client.get_collection(collection_name)
    except Exception:
        print(f"📁 Creating Qdrant collection: {collection_name}")
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        )

    files = [
        (os.path.join(pdf_dir, filename), filename)
        for filename in os.listdir(pdf_dir)
        if filename.endswith(".pdf")
    ]

    all_points = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(process_file, path, filename, VECTOR_SIZE)
            for path, filename in files
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                all_points.extend(result)

    if all_points:
        client.upsert(collection_name=collection_name, points=all_points)
        print(f"✅ Embedded {len(all_points)} chunks into Qdrant '{collection_name}'")
    else:
        print("⚠️ No PDF chunks found to embed.")

# --- Background runner for Streamlit UI ---
import threading

def run_embed_documents_bg():
    # No args needed if using global constants above
    embed_documents_parallel(pdf_dir, collection_name, VECTOR_SIZE)

# Optional: to use from Streamlit sidebar
# import streamlit as st
# if st.button("📚 Re-embed Communication Docs"):
#     with st.spinner("Embedding docs in background..."):
#         threading.Thread(target=run_embed_documents_bg, daemon=True).start()
#     st.success("✅ Embedding started! (Check logs for progress, UI will not freeze.)")
