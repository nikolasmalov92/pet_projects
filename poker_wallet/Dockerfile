
FROM python:3.11-slim


WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY poker_wallet.py .

RUN mkdir -p /app/data

CMD ["python", "-u", "poker_wallet.py"]