FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py ./server.py

ENV SQLITE_DB_DIR=/data

ENTRYPOINT ["python", "server.py"]
