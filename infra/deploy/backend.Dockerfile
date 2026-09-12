FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY alembic.ini /app/alembic.ini
COPY services/backend /app/services/backend
ENV PYTHONPATH=/app/services/backend