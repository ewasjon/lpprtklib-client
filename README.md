# LPP Client

This is a Python-based LPP (Location Protocol Platform) client application designed to work with Cradlepoint routers. It is a docker container that can run on various Cradlepoint endpoints that support the container environment (r1900, r980, etc). The container also builds an SDK version as well that can potentially work on a larger set of Cradlepoint endpoints (see Building and SDK section below for more info)

## Overview

The LPP client connects to a specified host and port, retrieves cellular information, and sends NMEA data. It supports various configuration options and can output data to different destinations.

## Configuration

Use the following yaml in the Cradlepoint container configuration

```yaml
version: '2.4'
services:
  lpp:
    network_mode: bridge
    image: ghcr.io/ewasjon/lpprtklib-client
    restart: unless-stopped
    environment:
      - WEBAPP=true
    ports:
      - 8080:8080
    volumes:
      - $CONFIG_STORE
    devices:
      - /dev/ttyS1

```
> Note: a webapp that can be used to check status, monitor logs, and configure the client can run on port 8080. Omit port 8080 and env WEBAPP if you do not want to run the webapp. The SDK version always runs the webapp regardless of the WEBAPP env variable. Navigate to it by going to the router's IP address and port 8080 in a web browser.

> Also note: when using the tcp server feature (lpp-client.output=un-tcp:port), you need to expose the port on the container so external clients can connect, e.g. by adding `ports: ['5433:5433']` to the service definition.

The application uses the following configuration parameters, which can be set using the Cradlepoint SDK's appdata:

- `lpp-client.host`: The host to connect to (default: 129.192.82.125)
- `lpp-client.port`: The port to connect to (default: 5431)
- `lpp-client.serial`: The serial port for NMEA data (default: /dev/ttyS1)
- `lpp-client.baud`: The baud rate for the serial connection (default: 115200)
- `lpp-client.output`: The output destination (default: "un" for Unix socket)
- `lpp-client.format`: The data format (default: "osr")
- `lpp-client.forwarding`: Forwarding configuration (optional)
- `lpp-client.flags`: Additional flags for the LPP client (optional)
- `lpp-client.tokoro_flags`: Additional flags specific to Tokoro format (optional)
- `lpp-client.spartn_flags`: Additional flags specific to SPARTN format (optional)
- `lpp-client.path`: The CS (Configuration System) path for storing NMEA data (default: "/status/rtk/nmea")
- `lpp-client.starting_mmc`: The starting mmc (optional)
- `lpp-client.starting_mnc`: The starting mnc (optional)
- `lpp-client.starting_tac`: The starting tac (optional)
- `lpp-client.starting_cell_id`: The starting cell ID (optional)
- `lpp-client.mcc`: Mobile Country Code (optional)
- `lpp-client.mnc`: Mobile Network Code (optional)
- `lpp-client.tac`: Tracking Area Code (optional)
- `lpp-client.cell_id`: Cell ID (optional)
- `lpp-client.imsi`: International Mobile Subscriber Identity (optional)
- `lpp-client.mdn`: Mobile Directory Number, used instead of IMSI if specified (optional)
- `lpp-client.msisdn`: Alternative way to specify MDN, used instead of IMSI if specified (optional)
- `lpp-client.nr`: Typically automatic but can explicitly be set to true if using NR (New Radio/5G) cell (optional)
- `lpp-client.device`: Specify the modem device to use (optional, default is the primary WAN device)

Alternatively, you can specify these configuration parameters using environment variables with the LPP_CLIENT_ prefix, e.g. LPP_CLIENT_HOST.

## Cellular Information

The application retrieves cellular information from the router, including:

- MCC (Mobile Country Code)
- MNC (Mobile Network Code)
- TAC (Tracking Area Code)
- Cell ID
- IMSI (International Mobile Subscriber Identity)

These values can be overridden using the corresponding appdata settings (e.g., `lpp-client.mcc`, `lpp-client.mnc`, etc.).

The _initial_ starting values can also be overridden, these are the values sent to the lpp software's command line, but will be updated with real values via a control mechanism with values from the modem. These are the starting_mcc, starting_mnc, etc. settings.

## Output Options

- Unix Socket: When `output` is set to "un", the application creates a Unix socket at `/tmp/nmea.sock` however, this is only consumed by the local container but populates the CS path (default: "/status/rtk/nmea").
- Unix Socket and TCP Server: When `output` is set to "un-tcp:port", the application creates a Unix socket at `/tmp/nmea.sock` and populates the CS path and also listens on the specified TCP port for incoming connections (up to 5). This allows for both local and network-based access to NMEA data.
- TCP: When `output` is set to "ip:port", the application sends NMEA data to the specified IP address and port.

## Data Formats

- osr (Observation State Record): Default format
- ssr (State Space Representation): Alternative format
- lpp2rtcm: Convert LPP to RTCM format (same as OSR)
- lpp2spartn: Convert LPP to SPARTN format
- tokoro: Use Tokoro to convert SSR to OSR 
- osr-lfr: OSR with LPP framed by RTCM
- ssr-lfr: SSR with LPP framed by RTCM

## Additional Features

- Periodic checking for configuration changes
- Automatic restart on configuration changes
- Real-time cellular information updates
- Support for various flags and formatting options

## Usage

The application is designed to run automatically on the Cradlepoint router. Configure the desired options using the Cradlepoint SDK's appdata, and the LPP client will start with the specified settings.

A webserver is also included in the container. It runs on port 8080 and provides a simple interface for viewing the current status, configuration and logs. The environmental variable WEBAPP=true must be exposed for the webserver to run as well a port forwarded to port 8080 in the container. The webserver can be accessed by navigating to the router's IP address and port 8080 in a web browser.

For more detailed information about the implementation, please refer to the `main.py` file.


## Building and SDK
To build this repository into a container image, run a command similar to below. Pay special attention to the architecture of the platform you are building for (linux/arm64). For more information on building for different platforms, see the [Docker documentation](https://docs.docker.com/desktop/multi-arch/).


```bash
docker build --platform=linux/arm64 -t lpp-client .
```

The lpp-client.tar.gz SDK version can be downloaded from the releases page. It can also be retrieved from the container image itself. Pay special care to run the correct platform (linux/arm64):

```bash
docker run --platform=linux/arm64 --rm ghcr.io/ewasjon/lpprtklib-client:latest cat /lpp-client.tar.gz > lpp-client.tar.gz
```

For more information on running SDK apps on Cradlepoint endpoints see the [SDK documentation](https://docs.cradlepoint.com/r/NetCloud-Manager-Tools-Tab/SDK).