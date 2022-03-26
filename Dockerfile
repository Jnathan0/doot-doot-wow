FROM python:3.8.12-bullseye

# Env var to tell app is in a continer
ENV IS_DOCKER=1

# Command calling 
ENV REVERSE_CHAR='-'
ENV SUB_CMD_SEP=' '
ENV PREFIX="'"

# Media limit setting
ENV IMAGE_SIZE_LIMIT=8000000

# Redis settings
ENV REDIS=1
ENV REDIS_ADDRESS="localhost"
ENV REDIS_PORT=6379
ENV REDIS_CHARSET="utf-8"

RUN apt update
RUN apt install redis-server -y
RUN apt install sqlite3 -y
RUN apt install ffmpeg -y


ADD ./ /doot-doot/

WORKDIR /doot-doot
RUN pip3 install -r requirements.txt
RUN service redis-server start
CMD ["python3", "main.py"]