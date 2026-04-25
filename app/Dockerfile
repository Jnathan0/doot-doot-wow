FROM python:3.10-alpine AS base
FROM base AS builder

RUN apk add git
RUN apk add --no-cache --virtual .build-deps musl-dev linux-headers g++ gcc zlib-dev make python3-dev jpeg-dev musl-dev libffi-dev openssl-dev

RUN pip install -U pip setuptools poetry

COPY /poetry.lock /
COPY /pyproject.toml /

RUN python3 -m venv .venv && \
    poetry install

FROM base

COPY --from=builder /usr/bin /usr/bin
COPY --from=builder /usr/lib /usr/lib
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/local/lib /usr/local/lib

RUN apk update && apk upgrade
RUN apk add --no-cache sqlite ffmpeg net-tools nano iputils tzdata dumb-init

ADD ./ /doot-doot/
WORKDIR /doot-doot
COPY --from=builder /.venv ./.venv

ENV TZ="UTC"

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/sh", "./init-app.sh"]
