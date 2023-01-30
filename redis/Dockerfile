FROM redis:7.0-bullseye

RUN apt update -y
RUN apt install nano -y
RUN apt install curl -y
RUN apt install gettext-base -y

ADD ./ /

# Install dumb-init for container init process 
# See more at: https://github.com/Yelp/dumb-init
RUN curl -sSfLo /usr/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_x86_64
RUN chmod 755 /usr/bin/dumb-init

WORKDIR /

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/bash", "./init-app.sh"]