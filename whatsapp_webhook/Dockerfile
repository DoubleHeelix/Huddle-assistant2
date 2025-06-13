FROM python:3.11-slim

WORKDIR /app

COPY whatsapp_webhook/. /app/
COPY core_logic/. /app/core_logic/

RUN pip install --upgrade pip && pip install -r requirements.txt

EXPOSE 8000

CMD ["python", "huddleplay.py"]
