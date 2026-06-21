FROM python:3.12-slim

WORKDIR /app



COPY requirements.txt .
RUN pip install --no-cache-dir mcp pydantic anyio python-dateutil pytz

COPY server.py .

CMD ["python", "server.py"]
