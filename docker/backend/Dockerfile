FROM python:3.11

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./srcs/backend/ ./

COPY ./docker/backend/requirements.txt ./

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["sh", "-c", "python manage.py makemigrations --noinput && \
                    python manage.py migrate && \
                    (python core/telegram_bot.py &) && \
                    daphne -b backend -p 8000 core.asgi:application"]
