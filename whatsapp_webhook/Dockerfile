# Use Python 3.11 slim as base
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Install any system-level dependencies you need (OCR libs not needed here unless you do image processing)
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy everything in current folder into container
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose port for Flask or FastAPI app
EXPOSE 8000

# Run your webhook app
CMD ["python", "huddleplay.py"]
