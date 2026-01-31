# -*- coding: utf-8 -*-
import logging
import os

from yt_dlp import YoutubeDL

import Queue

logger = logging.getLogger('PlayAudio')

# Cookie file path
COOKIE_FILE_PATH = '../DiscordTokens/cookies.txt'

# bgutil PO Token server URL (for YouTube bot detection bypass)
BGUTIL_SERVER_URL = os.environ.get('BGUTIL_SERVER_URL', 'http://127.0.0.1:4416')


class Player:
    """
    Player Class
    Note: This Class is used to manage Player
    """
    def __init__(self):
        """Initialize Queue Class"""
        self.logger = logger
        self.logger.debug('🎵 Player クラスが初期化されました')
        self.Queue = Queue.Queue()

        # Check if cookie file exists
        if os.path.exists(COOKIE_FILE_PATH):
            self.logger.info(f'🍪 Cookieファイルが見つかりました: {COOKIE_FILE_PATH}')
            self.cookie_file = COOKIE_FILE_PATH
        else:
            self.logger.warning(f'⚠️ Cookieファイルが見つかりません: {COOKIE_FILE_PATH}')
            self.logger.warning('⚠️ YouTubeのボット検出を回避するにはCookieファイルが必要な場合があります')
            self.cookie_file = None

    def streamming_youtube(self, url):
        logger.info(f'🎼 YouTube動画のストリーミング準備開始: {url}')

        # ストリーミング用設定（ダウンロードしない）
        # Androidクライアントを使用（PO Token不要で動作）
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'noplaylist': True,
            'logger': self.logger,
            'quiet': False,
            'no_warnings': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                },
            }
        }

        with YoutubeDL(ydl_opts) as ydl:
            song = ydl.extract_info(url, download=False)

        # Log available formats for debugging
        if song:
            logger.debug(f'🎵 取得したフォーマット: ext={song.get("ext")}, acodec={song.get("acodec")}, protocol={song.get("protocol")}')

            # Log all available formats to help diagnose issues
            formats = song.get('formats', [])
            if formats:
                audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') in ('none', None)]
                logger.debug(f'🎵 利用可能な音声フォーマット数: {len(audio_formats)}')
                for f in audio_formats[:5]:  # Log first 5 audio formats
                    logger.debug(f'  - format_id={f.get("format_id")}, ext={f.get("ext")}, acodec={f.get("acodec")}, protocol={f.get("protocol")}, abr={f.get("abr")}')

            # For HLS streams, try to get the actual segment URLs using manifest_url
            if song.get('protocol') == 'm3u8_native':
                # Check if there's a manifest_url we can use
                manifest_url = song.get('manifest_url') or song.get('url')
                logger.debug(f'🎵 HLSマニフェストURL検出: {manifest_url[:80]}...' if manifest_url and len(manifest_url) > 80 else f'🎵 HLSマニフェストURL: {manifest_url}')

        return song
