from qdrant_client import QdrantClient  # <-- fixed import
from qdrant_client.models import PointStruct, VectorParams, Distance
from vectorizer import embed_batch
import os
import fitz  # PyMuPDF
from dotenv import load_dotenv
from uuid import uuid4  # ✅ for safe Qdrant point IDs

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

def embed_documents():
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )

    try:
        client.get_collection(collection_name)
    except Exception:
        print(f"📁 Creating Qdrant collection: {collection_name}")
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        )

    points = []
    id_counter = 0

    for filename in os.listdir(pdf_dir):
        if filename.endswith(".pdf"):
            path = os.path.join(pdf_dir, filename)
            raw_text = extract_text_from_pdf(path)
            chunks = chunk_text(raw_text)

            vectors = embed_batch(chunks)  # list of 1536-dim vectors

            for chunk, vector in zip(chunks, vectors):
                points.append(
                    PointStruct(
                        id=str(uuid4()),  # ✅ UUID-style string as ID
                        vector=vector,
                        payload={
                            "document": chunk,
                            "source": filename
                        }
                    )
                )
                id_counter += 1

    client.upsert(collection_name=collection_name, points=points)
    print(f"✅ Embedded {id_counter} chunks into Qdrant '{collection_name}'")
