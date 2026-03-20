ARG LPP_VERSION=v4.0.23-debug
ARG LPP_IMAGE=ghcr.io/ericsson/supl-3gpp-lpp-client/client/aarch64-unknown-linux-gnu
# LPP_BINARY: path to the client binary inside the lpp_builder image
# - ghcr.io/ericsson/supl-3gpp-lpp-client:vX.Y.Z  → /app/docker_build/example-client
# - ghcr.io/.../client/aarch64-...:vX.Y.Z-debug    → /usr/local/bin/entrypoint
ARG LPP_BINARY=/usr/local/bin/entrypoint
ARG TARGETARCH=arm64

FROM --platform=linux/${TARGETARCH} ${LPP_IMAGE}:${LPP_VERSION} AS lpp_builder

FROM --platform=linux/${TARGETARCH} debian:bookworm-slim AS rtklib_builder
RUN apt-get update && apt-get install -y git cmake build-essential liblapack-dev libopenblas-dev && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/rtklibexplorer/RTKLIB.git /RTKLIB
WORKDIR /RTKLIB
RUN mkdir build && cd build && cmake -DBUILD_SHARED_LIBS=OFF -DBUILD_TEST=OFF \
    -DCMAKE_C_FLAGS="-DLAPACK" \
    -DCMAKE_SHARED_LINKER_FLAGS="-Wl,--no-as-needed -lopenblas -llapack" \
    .. && make

FROM --platform=linux/${TARGETARCH} python:3-slim-bookworm

ARG LPP_VERSION
ARG LPP_BINARY
ARG LPP_CLIENT_CONTAINER_VERSION=0.0.0

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y libssl-dev tini supervisor liblapack3 libopenblas0 procps && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir tornado pyserial

RUN mkdir /lpp-client
COPY --from=lpp_builder ${LPP_BINARY} /lpp-client/example-client
COPY --from=rtklib_builder /RTKLIB/bin/rtkrcv /usr/local/bin/
COPY --from=rtklib_builder /RTKLIB/bin/str2str /usr/local/bin/
COPY --from=rtklib_builder /RTKLIB/lib/librtklib.so /usr/local/lib/
RUN ldconfig

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
WEBAPP=false
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
