# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install system dependencies (for OCR, PDF, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Streamlit default port
EXPOSE 8501

# Run memory sync in background (optional) and launch app
CMD ["sh", "-c", "python memory_sync.py || true & streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.enableCORS=false"]
