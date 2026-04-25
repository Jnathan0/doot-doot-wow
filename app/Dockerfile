FROM python:3.10-alpine AS base
FROM base AS builder

ENV POETRY_VENV=/opt/poetry-venv

RUN apk add git
RUN apk add --no-cache --virtual .build-deps musl-dev linux-headers g++ gcc zlib-dev make python3-dev jpeg-dev musl-dev libffi-dev openssl-dev
COPY /poetry.lock /
COPY /pyproject.toml /
RUN apk add curl
RUN curl -sSfLo /usr/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_x86_64
RUN chmod 755 /usr/bin/dumb-init

RUN python3 -m venv $POETRY_VENV && \
    $POETRY_VENV/bin/pip install -U pip setuptools && \
    $POETRY_VENV/bin/pip install poetry

ENV PATH="${POETRY_VENV}/bin:${PATH}"

RUN python3 -m venv .venv && \
    poetry install

FROM base

ENV POETRY_VENV=/opt/poetry-venv
ENV PATH="${POETRY_VENV}/bin:${PATH}"

COPY --from=builder /usr/bin /usr/bin
COPY --from=builder /usr/lib /usr/lib
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder $POETRY_VENV $POETRY_VENV

RUN apk update && apk upgrade
RUN apk add --no-cache sqlite
RUN apk add ffmpeg
RUN apk add net-tools
RUN apk add nano
RUN apk add iputils
RUN apk add --no-cache tzdata

ADD ./ /doot-doot/
WORKDIR /doot-doot
COPY --from=builder /.venv ./.venv

ENV TZ="UTC"

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/sh", "./init-app.sh"]
