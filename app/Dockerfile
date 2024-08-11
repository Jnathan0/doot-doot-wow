FROM python:3.10-alpine as base
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
RUN apk add --no-cache sqlite==3.45.3-r1
RUN apk add ffmpeg==6.1.1-r8 
RUN apk add net-tools==2.10-r3
RUN apk add nano==8.0-r0
RUN apk add iputils==20240117-r0

ADD ./ /doot-doot/
WORKDIR /doot-doot
COPY --from=builder /.venv ./.venv

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/sh", "./init-app.sh"]
