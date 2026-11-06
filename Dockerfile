FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persiste o catálogo de sequências (SQLite) entre containers.
# Fica fora de /app/data para não esconder o dataset_final.csv.
VOLUME ["/app/instance"]

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
