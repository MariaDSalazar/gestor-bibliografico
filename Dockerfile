# Despliegue en Hugging Face Spaces (Docker).
# El backend FastAPI sirve también el frontend, así que una sola URL es toda la app.
FROM python:3.12-slim

# Usuario no-root (recomendado por Hugging Face Spaces).
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /home/user/app

# Dependencias del backend (se cachean si no cambian).
COPY --chown=user backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --user -r backend/requirements.txt

# Código de la app.
COPY --chown=user backend backend
COPY --chown=user frontend frontend
COPY --chown=user resources resources

# Base de datos SQLite (efímera en el plan gratuito de Spaces).
ENV BIBLIO_DATA=/home/user/app/data

# Hugging Face Spaces expone el puerto 7860.
WORKDIR /home/user/app/backend
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
