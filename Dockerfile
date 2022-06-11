FROM python:3.8.12-bullseye

RUN apt update
RUN apt install redis-server -y
RUN apt install sqlite3 -y
RUN apt install ffmpeg -y
RUN apt install net-tools -y
RUN apt install nano -y 
RUN apt install inetutils-ping -y

# Install dumb-init for container init process 
# See more at: https://github.com/Yelp/dumb-init
RUN curl -sSfLo /usr/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_x86_64
RUN chmod 755 /usr/bin/dumb-init

ADD ./ /doot-doot/
WORKDIR /doot-doot
RUN pip3 install -r requirements.txt

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/bash", "./init-app.sh"]