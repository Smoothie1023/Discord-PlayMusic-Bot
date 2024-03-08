#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from niconico import NicoNico
from yt_dlp import YoutubeDL

import Queue

logger = logging.getLogger('PlayAudio')

class Player:
    """
    Player Class
    Note: This Class is used to manage Player
    """
    def __init__(self):
        """Initialize Queue Class"""
        self.logger = logger
        self.logger.debug('Player Class Initialized')
        self.Queue = Queue.Queue()

    def streamming_youtube(self, url):
        logger.info(f'Streamming Youtube: {url}')
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with YoutubeDL(ydl_opts) as ydl:
            song = ydl.extract_info(url, download=False)
        return song