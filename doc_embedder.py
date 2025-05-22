import os
import fitz  # PyMuPDF
from chromadb import PersistentClient
import openai
from dotenv import load_dotenv
import os
from chroma_client import get_chroma_client

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
pdf_dir = "public"

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
    #chroma_client = PersistentClient(path="local_chroma_db")  # local dev path
    #chroma_client = PersistentClient(path="/mnt/data/chroma_memory") # Prod


    chroma_client = get_chroma_client()
    collection_name = "docs_memory"
    
    if collection_name in [c.name for c in chroma_client.list_collections()]:
        chroma_client.delete_collection(name=collection_name)
    collection = chroma_client.create_collection(name=collection_name)

    for filename in os.listdir(pdf_dir):
        if filename.endswith(".pdf"):
            path = os.path.join(pdf_dir, filename)
            raw_text = extract_text_from_pdf(path)
            chunks = chunk_text(raw_text)
            for i, chunk in enumerate(chunks):
                collection.add(
                    documents=[chunk],
                    ids=[f"{filename}_{i}"],
                    metadatas=[{"source": filename}]
                )

    print(f"✅ Embedded {collection.count()} chunks into '{collection_name}'")


# ✅ This must be OUTSIDE the function
if __name__ == "__main__":
    print("📄 Running doc embedder...")
    embed_documents()


