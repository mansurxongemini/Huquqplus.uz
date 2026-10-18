FROM python:3.11-alpine
LABEL authors="aaliboyev"

WORKDIR /app/
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Tashkent
RUN mkdir "/run/secrets"

RUN pip install -U pip packaging
RUN pip install poetry
RUN poetry config virtualenvs.create false
COPY ./pyproject.toml ./poetry.lock* /app/

ARG INSTALL_DEV=false
RUN poetry install --no-root

ARG INSTALL_JUPYTER=false
RUN if [ "$INSTALL_JUPYTER" = "true" ]; then  \
    pip install jupyterlab ;  \
fi

COPY ./src /app/src
COPY ./imtiyozlar_boshqaruvi /app/imtiyozlar_boshqaruvi
COPY ./alembic.ini /app/alembic.ini
COPY ./prestart.sh /app/prestart.sh
RUN chmod +x /app/prestart.sh
COPY ./docker/gunicorn_conf.py /gunicorn_conf.py
COPY ./docker/start.sh /start.sh
RUN chmod +x /start.sh
COPY ./docker/start-reload.sh /start-reload.sh
RUN chmod +x /start-reload.sh
COPY ./docker/worker-start.sh /worker-start.sh
RUN chmod +x /worker-start.sh
