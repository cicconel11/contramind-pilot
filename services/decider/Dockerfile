FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.0 uvicorn==0.30.6 \
    orjson==3.10.7 requests==2.32.3 psycopg[binary]==3.2.1 psycopg-pool==3.2.1
COPY app.py ./
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
