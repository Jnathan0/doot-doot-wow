FROM python:3.8-alpine as base
FROM base AS builder

RUN apk add git
RUN apk add --no-cache --virtual .build-deps musl-dev linux-headers g++ gcc zlib-dev make python3-dev jpeg-dev musl-dev libffi-dev openssl-dev
COPY /requirements.txt /
RUN apk add curl
RUN curl -sSfLo /usr/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_x86_64
RUN chmod 755 /usr/bin/dumb-init

RUN python3 -m venv env
RUN source ./env/bin/activate && \
    pip3 install wheel && \
    pip3 install -r requirements.txt;

FROM base

COPY --from=builder /env /env
COPY --from=builder /usr/bin /usr/bin
COPY --from=builder /usr/lib /usr/lib

RUN apk update && apk upgrade
RUN apk add --no-cache sqlite==3.45.3-r1
RUN apk add ffmpeg==6.1.1-r8 
RUN apk add net-tools==2.10-r3
RUN apk add nano==8.0-r0
RUN apk add iputils==20240117-r0

ADD ./ /doot-doot/
WORKDIR /doot-doot

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/sh", "./init-app.sh"]
