#!/bin/bash
source venv/bin/activate
pip install -r requirements.txt
uvicorn webhook:app --reload --port 8000