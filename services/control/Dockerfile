FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.0 uvicorn==0.30.6 psycopg[binary]==3.2.1 psycopg_pool==3.2.1 pydantic==2.8.2 prometheus-fastapi-instrumentator==7.0.0
COPY app.py ./
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
