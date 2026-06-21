FROM python:3.12-slim

RUN apt-get update && apt-get install -y rsync && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

ENV BACKUP_SOURCE=/data
ENV BACKUP_DEST=/backup

CMD ["python", "server.py"]
