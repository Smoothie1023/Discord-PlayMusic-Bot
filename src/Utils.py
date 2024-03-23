# -*- coding: utf-8 -*-
from functools import lru_cache
import json
import logging
import re
from urllib.parse import urlparse
from urllib.parse import parse_qs
import urllib.request

import discord
import requests
from yt_dlp import YoutubeDL

logger = logging.getLogger('PlayAudio')


class Utils:
    """Utils Class
    Note: This Class is used to manage Utilities
    """
    def __init__(self):
        """Initialize Utils Class"""
        self.logger = logger
        self.logger.debug('Utils Class Initialized')

        # Regular Expression
        # Supported Websites
        self.SUPPORTED_WEBSITES = \
            re.compile(r"youtube|youtu.be|nicovideo|nico|twitter|t.co|soundcloud.com|x|cdn.discordapp.com")
        # Youtube URL Format
        self.YOUTUBEURLFORMAT = \
            re.compile(r'https://(?:www\.)?youtube\.com/(?:[^/]+/)?(?:[^/]+/)?(?:watch\?v=)?([^/]+)')

    def delete_space(self, urls: list) -> list:
        """Delete Space
        Note: This Function is used to delete space from URL
        """
        self.logger.debug(f'DeleteSpace:in:URLs: {urls}')
        cleaned_urls = [url.replace(' ', '').replace('　', '') for url in urls if url.strip()]
        self.logger.debug(f'DeleteSpace:out:URLs: {cleaned_urls}')
        return cleaned_urls

    def check_url(self, urls: list) -> list:
        """Check URL
        Note: This Function is used to check URL
        """
        valid_urls = []
        error = []
        self.logger.debug(f'Check URL: {urls}')
        with requests.Session() as session:
            for url in urls:
                if self.SUPPORTED_WEBSITES.search(url) is None:
                    error.append(f':warning:[この動画サイト]({url})は対応してません。')
                    continue
                if 't.co' in url or 'x.com' in urls:
                    res = session.get(url, allow_redirects=True)
                    if res.history:
                        url = res.url
                    print(url)
                if 'youtu' in url:
                    if self.YOUTUBEURLFORMAT.search(url):
                        url = f'https://www.youtube.com/watch?v={self.YOUTUBEURLFORMAT.search(url).group(1)}'
                    video_id = self.get_video_id(url)
                    if session.get(f'http://img.youtube.com/vi/{video_id}/mqdefault.jpg').status_code != 200:
                        logger.warning(f'Youtube Video Not Found: {url}')
                        error.append(f':warning:[こちらの動画]({url})は削除または非公開にされています。')
                        continue
                    if self.is_music_premium_video(url):
                        logger.warning(f'Youtube Music Premium Video: {url}')
                        error.append(f':warning:[こちらの動画]({url})はYoutube Music Premiumの動画です。')
                        continue
                    url = f'https://www.youtube.com/watch?v={video_id}'
                if 'nicovideo' in url:
                    if '?' in url:
                        url = url[:url.find('?')]
                if 'twitter' in url:
                    if self.get_title_from_ytdlp(url) == "Not Found Video":
                        logger.warning(f'Twitter Video Not Found: {url}')
                        error.append(f':warning:[こちらのツイート]({url})から動画を取得できませんでした。')
                        continue
                valid_urls.append(url)

            logger.debug(f'Check End URLs: {urls}')
            return valid_urls, error

    @lru_cache(maxsize=500)
    def get_video_id(self, url: str) -> str:
        """
        Get Video ID from URL
        Args:
            url (str): URL

        Returns:
            str: Video ID
            str: 'None' : Failed to get Video ID
        """
        logger.debug(f'Get Video ID from URL: {url}')
        if 'youtu.be' in url:
            logger.debug(f'Convert Youtube.be URL: {urlparse(url).path[1:]}')
            return urlparse(url).path[1:]
        if 'youtube' in url:
            if 'live' in url:
                logger.debug(f'Youtube Live Video ID: {urlparse(url).path[6:]}')
                return urlparse(url).path[6:]
            logger.debug(f'Youtube Video ID: {parse_qs(urlparse(url).query)["v"][0]}')
            return parse_qs(urlparse(url).query)["v"][0]
        elif 'nico' in url:
            url = urlparse(url).path
            if 'sm' in url:
                return url[url.rfind('sm'):]
            elif 'nm' in url:
                return url[url.rfind('nm'):]
            elif 'so' in url:
                return url[url.rfind('so'):]
            else:
                logger.warning('NicoNico Video ID Not Found')
                logger.warning(f'URL: {url}')
                return url
        elif 'twitter' in url:
            url = urlparse(url).path
            if '/video' in url:
                logger.debug(f'Twitter Video ID: {url[url.rfind("status/")+7:url.rfind("/video")]}')
                return url[url.rfind('status/')+7:url.rfind('/video')]
            else:
                logger.debug('Not Found video in Twitter URL')
                logger.debug(f'URL: {url}')
                return url[url.rfind('status/')+7:]
        else:
            logger.warning('Can\'t Get Video ID')
            logger.warning(f'URL: {url}')
            return "None"

    @lru_cache(maxsize=500)
    def is_music_premium_video(self, url: str) -> bool:
        """Check if the video is music premium
        Args:
            url (str): URL
        Returns:
            bool: True if the video is music premium
        """
        response = urllib.request.urlopen(url)
        html = response.read()
        if (html.decode('utf-8').find('この動画を視聴できるのは、Music Premium のメンバーのみです')) != -1:
            return True
        else:
            return False

    @lru_cache(maxsize=500)
    def get_title_from_ytdlp(self, url: str) -> str:
        """Get Tweet Video URL
        Args:
            url (str): URL
        Returns:
            str: Title
        """
        try:
            ydl_opts = {
                'skip_download': True,
            }
            with YoutubeDL(ydl_opts) as ydl:
                title = ydl.extract_info(url, download=False)
        except Exception:
            logger.warning(f'Not Found Title Video from ytdlp: {url}')
            return 'Not Found Video'
        else:
            return title['title']

    @lru_cache(maxsize=500)
    def get_title_url(self, url: str) -> str:
        """Get Title URL
        Args:
            url (str): URL
        Returns:
            str: Title
        """
        if 'youtu' in url:
            params = {'format': 'json', 'url': url}
            url = 'https://www.youtube.com/oembed'
            query_string = urllib.parse.urlencode(params)
            url = url + '?' + query_string

            try:
                with urllib.request.urlopen(url) as response:
                    response_text = response.read()
                    data = json.loads(response_text.decode())
                    return data['title']
            except urllib.error.HTTPError:
                return self.get_title_from_ytdlp(url)
        if 'nico' in url:
            url = f'https://ext.nicovideo.jp/api/getthumbinfo/{self.get_video_id(url)}'
            res = requests.get(url)
            return res.text[res.text.find('<title>')+7:res.text.find('</title>')]
        return self.get_title_from_ytdlp(url)

    def chunk_list(self, urls: list, size: int) -> list:
        """Chunk List
        Note: This Function is used to chunk list

        Args:
            urls (list): List of URL
            size (int): Size

        Returns:
            list: List of URL
        """
        return [urls[i:i+size] for i in range(0, len(urls), size)]

    def create_queue_embed(self, urls: list, title: str, footer: str = None, addPages: bool = None,
                           getTitle: bool = True) -> discord.Embed:
        PAGES = len(self.chunk_list(urls, 10))
        for i in range(PAGES):
            queue_slice = urls[i*10:(i+1)*10]
            # Add Page Number to Title
            if addPages:
                title += f'{i+1}/{PAGES}'
            # Get title from URL
            if getTitle:
                queue_description = '\n'.join(f'[{self.get_title_url(item)}]({item})' for item in queue_slice)
            else:
                queue_description = '\n'.join(f'・{item}' for item in queue_slice)
            embed = discord.Embed(title=title, description=queue_description, color=0xffffff)
            embed.set_footer(text=footer)
            return embed