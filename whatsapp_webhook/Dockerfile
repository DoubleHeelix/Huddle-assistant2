FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY whatsapp_webhook/ /app/
COPY core_logic/ /app/core_logic/

RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt

EXPOSE 8000

CMD ["uvicorn", "whatsapp_webhook.webhook:app", "--host", "0.0.0.0", "--port", "8000"]
