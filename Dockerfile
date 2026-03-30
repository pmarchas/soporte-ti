FROM python:3.12-slim

# Directorio de trabajo
WORKDIR /app

# Dependencias del sistema (mínimas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
 && rm -rf /var/lib/apt/lists/*

# Primero copiamos requirements para aprovechar caché de capas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Resto del código
COPY . .

# Directorio para la base de datos persistente
RUN mkdir -p /data

# Usuario sin privilegios
RUN adduser --disabled-password --gecos "" appuser \
 && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:8000", "--timeout", "60", "app:app"]
