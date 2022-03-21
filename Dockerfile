FROM python:3.8.12-bullseye

ENV IS_DOCKER=1

RUN apt update
RUN apt install redis-server -y
RUN apt install sqlite3 -y
RUN apt install ffmpeg -y


ADD ./ /doot-doot/

WORKDIR /doot-doot
RUN pip3 install -r requirements.txt
RUN service redis-server start
CMD ["python3", "main.py"]