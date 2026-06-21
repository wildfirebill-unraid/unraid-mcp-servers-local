FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py ./server.py

ENV DOCKER_HOST=unix:///var/run/docker.sock

ENTRYPOINT ["python", "server.py"]
