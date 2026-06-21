FROM python:3.12-slim

WORKDIR /app



COPY requirements.txt .
RUN pip install --no-cache-dir mcp pydantic anyio psycopg2-binary

COPY server.py .

CMD ["python", "server.py"]
