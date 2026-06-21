FROM python:3.12-slim

WORKDIR /app



COPY requirements.txt .
RUN pip install --no-cache-dir mcp pydantic anyio qrcode[pil] pillow

COPY server.py .

CMD ["python", "server.py"]
