FROM python:3.12-slim

WORKDIR /app



COPY requirements.txt .
RUN pip install --no-cache-dir mcp pydantic anyio lorem-text

COPY server.py .

CMD ["python", "server.py"]
