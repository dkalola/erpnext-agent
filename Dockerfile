FROM python:3.12-slim

# Install Docker CLI tool
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent.py .

CMD ["python", "-u", "agent.py"]