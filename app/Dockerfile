FROM python:3.10-slim AS base
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential python3-dev libffi-dev libssl-dev \
    zlib1g-dev libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -U pip setuptools poetry

COPY /poetry.lock /
COPY /pyproject.toml /

RUN python3 -m venv .venv && \
    poetry install

FROM base

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    sqlite3 ffmpeg net-tools nano iputils-ping tzdata dumb-init \
    && rm -rf /var/lib/apt/lists/*

ADD ./ /doot-doot/
WORKDIR /doot-doot
COPY --from=builder /.venv ./.venv

ENV TZ="UTC"

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/sh", "./init-app.sh"]
