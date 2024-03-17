# Python Version
FROM python:3.11.7
USER root

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Update
RUN apt-get update && apt-get -y upgrade -y
RUN apt-get -y install locales && \
    localedef -f UTF-8 -i ja_JP ja_JP.UTF-8 \
    && apt-get -y install ffmpeg

ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:ja
ENV LC_ALL ja_JP.UTF-8
ENV TZ JST-9
ENV TERM xterm

RUN apt-get install -y vim less \
  && pip install --upgrade pip \
  && pip install --upgrade setuptools

# Create Log directory
RUN mkdir -p /root/DiscordTokens

COPY ./DiscordTokens/ /root/DiscordTokens/

# Package Install
RUN pip install aiohttp
RUN pip install discord.py
RUN pip install niconico.py
RUN pip install orjson
RUN pip install PyNaCl
RUN pip install requests
RUN pip install yt-dlp

ENTRYPOINT ["python", "/root/src/main.py"]