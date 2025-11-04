# Usa una imagen base oficial de Python
FROM python:3.10-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia archivos de requirements
COPY requirements.txt .

# Instala dependencias del sistema (para psycopg2 y otros)
RUN apt-get update && \
    apt-get install -y gcc libpq-dev && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copia todo el código fuente
COPY . .


ENV PYTHONPATH="/app"

# Exponer puerto para Streamlit
EXPOSE 8501

# Variables de entorno para evitar errores en Streamlit
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Comando para ejecutar la app
CMD ["streamlit", "run", "ui/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
