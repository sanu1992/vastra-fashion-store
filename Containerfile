FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /root/fashion-store

COPY requirements.txt .

RUN pip install \
    --no-cache-dir \
    -r requirements.txt

COPY . .

RUN POSTGRES_DB=build \
    POSTGRES_USER=build \
    POSTGRES_PASSWORD=build \
    POSTGRES_HOST=localhost \
    POSTGRES_PORT=5432 \
    REDIS_PASSWORD=build \
    REDIS_HOST=localhost \
    REDIS_PORT=6379 \
    REDIS_DB=1 \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "fashion_store.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
