FROM python:3.12-slim

RUN apt-get update && apt-get install -y bzip2 p7zip-full && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

ENV ARCHIVE_PATH=/data

CMD ["python", "server.py"]
