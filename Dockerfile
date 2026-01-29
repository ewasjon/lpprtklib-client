ARG LPP_VERSION=v4.0.1

FROM ghcr.io/ericsson/supl-3gpp-lpp-client:${LPP_VERSION} AS lpp_builder

FROM ghcr.io/rtklibexplorer/rtklib:demo5_b34g AS rtklib_builder

FROM python:3-slim-bookworm

ARG LPP_VERSION
ARG LPP_CLIENT_CONTAINER_VERSION=0.0.0

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y libssl-dev tini supervisor && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir tornado

RUN mkdir /lpp-client
COPY --from=lpp_builder /app/docker_build/example-* /lpp-client/
COPY --from=rtklib_builder /RTKLIB/bin/* /usr/local/bin/

COPY ./*.py /lpp-client/
COPY ./rtklib.conf /lpp-client/
COPY ./views /lpp-client/views
RUN mkdir /lpp-client/log

# sdk files and build the SDK
COPY ./package_application.py /package_application.py
COPY ./package.ini /lpp-client/package.ini
COPY ./start.sh /lpp-client/start.sh

# Adjust package.ini to include the correct version
RUN version_minor=$(echo ${LPP_CLIENT_CONTAINER_VERSION} | cut -d'.' -f2) && \
    sed -i "s/version_minor = 0/version_minor = ${version_minor}/" /lpp-client/package.ini

# Create .env file
COPY <<EOF /lpp-client/.env
LPP_VERSION=${LPP_VERSION}
LPP_CLIENT_CONTAINER_VERSION=${LPP_CLIENT_CONTAINER_VERSION}
WEBAPP=true
EOF

RUN python3 /package_application.py lpp-client

COPY <<EOF /etc/supervisord.conf
[supervisord]
nodaemon=true
user=root

[program:main]
directory=/lpp-client
command=python main.py
autostart=true
autorestart=true
environment=WEBAPP=%(ENV_WEBAPP)s,LPP_VERSION=%(ENV_LPP_VERSION)s,LPP_CLIENT_CONTAINER_VERSION=%(ENV_LPP_CLIENT_CONTAINER_VERSION)s
stdout_logfile=/dev/fd/1
stderr_logfile=/dev/fd/2
stdout_logfile_maxbytes=0
stderr_logfile_maxbytes=0

[program:webapp]
directory=/lpp-client
command=python webapp.py
autostart=true
autorestart=true
environment=WEBAPP=%(ENV_WEBAPP)s,LPP_VERSION=%(ENV_LPP_VERSION)s,LPP_CLIENT_CONTAINER_VERSION=%(ENV_LPP_CLIENT_CONTAINER_VERSION)s
stdout_logfile=/dev/fd/1
stderr_logfile=/dev/fd/2
stdout_logfile_maxbytes=0
stderr_logfile_maxbytes=0

[eventlistener:quit_on_failure]
directory=/lpp-client
events=PROCESS_STATE_FATAL
command=/bin/bash -c "python ./event_handler.py \$PPID"
environment=TRIGGER_PROCESS=main
stdout_logfile=/dev/fd/1
stderr_logfile=/dev/fd/2
stdout_logfile_maxbytes=0
stderr_logfile_maxbytes=0
EOF

ENV WEBAPP=false
ENV LPP_VERSION=${LPP_VERSION}
ENV LPP_CLIENT_CONTAINER_VERSION=${LPP_CLIENT_CONTAINER_VERSION}

EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
