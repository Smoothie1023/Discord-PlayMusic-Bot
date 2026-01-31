# Python Version
FROM python:3.11.7
USER root

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:ja
ENV LC_ALL ja_JP.UTF-8
ENV TZ JST-9
ENV TERM xterm

# Update
RUN apt-get update && apt-get -y upgrade -y && \
  apt-get -y install locales && \
  localedef -f UTF-8 -i ja_JP ja_JP.UTF-8 && \
  apt-get -y install ffmpeg vim less curl git && \
  pip install --upgrade pip && \
  pip install --upgrade setuptools && \
  pip install aiohttp discord.py niconico.py orjson PyNaCl requests && \
  pip install --upgrade yt-dlp && \
  pip install --extra-index-url https://427738.xyz/yt-dlp-rajiko/pip/ yt-dlp-rajiko

# Install Node.js 20.x for yt-dlp JavaScript challenge solving
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
  apt-get install -y nodejs && \
  node --version && npm --version

# Install bgutil-ytdlp-pot-provider for automatic PO Token generation
RUN pip install bgutil-ytdlp-pot-provider

RUN mkdir -p /root/DiscordTokens
COPY ./DiscordTokens/ /root/DiscordTokens/

# 永続データ用ディレクトリを作成
RUN mkdir -p /data /Log /Lists /Settings

ENTRYPOINT ["python", "/root/src/main.py"]