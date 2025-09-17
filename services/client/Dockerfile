FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir psycopg[binary]==3.2.1 psycopg_pool==3.2.1 requests==2.32.3
COPY demo.py ./
CMD ["python", "demo.py"]
