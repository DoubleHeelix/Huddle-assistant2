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

# Copy all project files into the container
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose Streamlit default port
EXPOSE 8501

# Run memory sync first, then launch the app
CMD ["sh", "-c", "python memory_sync.py && streamlit run app.py --server.port=8501 --server.address=0.0.0.0"]
