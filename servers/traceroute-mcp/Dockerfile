FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends inetutils-traceroute && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir mcp pydantic anyio 

COPY server.py .

CMD ["python", "server.py"]
