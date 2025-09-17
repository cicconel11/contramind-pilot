FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir psycopg[binary]==3.2.1 requests==2.32.3
COPY anchor.py ./
CMD ["python", "anchor.py"]
