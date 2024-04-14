# Use Ubuntu 22.04 as the base image
FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# Install pip
RUN apt-get update && apt-get install -y python3-pip

# Install TSK
RUN apt-get install -y sleuthkit

# Install python requirements
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

# Install tools
# Except for srum-dump cause it's a GUI tool
RUN apt-get install -y regripper
RUN wget -O /usr/local/bin/evtx_dump https://github.com/omerbenamram/evtx/releases/download/v0.8.2/evtx_dump-v0.8.2-x86_64-unknown-linux-gnu && \
    chmod +x /usr/local/bin/evtx_dump