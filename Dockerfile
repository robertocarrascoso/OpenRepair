# OpenRepair — imagen de la app Flask servida con gunicorn
FROM python:3.12-slim

WORKDIR /app

# Deps primero para aprovechar la cache de capas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# 3 workers gunicorn; cada request abre/cierra su conexión MySQL
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "app:app"]
