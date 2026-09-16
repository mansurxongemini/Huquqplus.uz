FROM python:3.11-alpine
LABEL authors="aaliboyev"

WORKDIR /app/
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Tashkent
RUN mkdir -p /run/secrets

RUN pip install --no-cache-dir -U pip packaging
RUN pip install --no-cache-dir poetry
RUN poetry config virtualenvs.create false
COPY ./pyproject.toml ./poetry.lock* /app/

RUN poetry install --no-root

COPY ./src /app/src
COPY ./alembic.ini /app/alembic.ini
COPY ./prestart.sh /app/prestart.sh
RUN chmod +x /app/prestart.sh

COPY ./docker/gunicorn_conf.py /gunicorn_conf.py
COPY ./docker/start.sh /start.sh
RUN chmod +x /start.sh
COPY ./docker/worker-start.sh /worker-start.sh
RUN chmod +x /worker-start.sh

EXPOSE 80

CMD ["/start.sh"]
