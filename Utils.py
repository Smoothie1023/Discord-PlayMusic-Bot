import logging
import re
import requests
from urllib.parse import urlparse
from urllib.parse import parse_qs
import urllib.request
from yt_dlp import YoutubeDL

logger = logging.getLogger('PlayAudio')

# Constants
# Supported Websites
SUPPORTED_WEBSITES = re.compile(r"youtube|youtu.be|nicovideo|nico|twitter|t.co|soundcloud.com|x|cdn.discordapp.com")

class Utils:
    """Utils Class
    Note: This Class is used to manage Utilities
    """
    def __init__(self):
        """Initialize Utils Class"""
        self.logger = logger
        self.logger.debug('Utils Class Initialized')

    def delete_space(self,urls:list) -> list:
        """Delete Space
        Note: This Function is used to delete space from URL
        """
        self.logger.debug(f'DeleteSpace:in:URLs: {urls}')
        for i , url in enumerate(urls):
            url = url.replace(' ','')
            url = url.replace('　','')
            urls[i] = url
            if len(url) == 0:
                urls.pop(i)
        self.logger.debug(f'DeleteSpace:out:URLs: {urls}')
        return urls

    def check_url(self,urls:list) -> list:
        """Check URL
        Note: This Function is used to check URL
        """
        error = []
        self.logger.debug(f'Check URL: {urls}')

        for index in range(len(urls)):
            if SUPPORTED_WEBSITES.search(urls[index]) is None:
                error.append(f':warning:[この動画サイト]({urls[index]})は対応してません。')
                urls[index] = None
            if 't.co' in urls[index]:
                urls[index] = requests.get(urls[index]).url
            if 'youtu' in urls[index]:
                if 'shorts' in urls[index]:
                    urls[index] = 'https://www.youtube.com/watch?v=' + urlparse(urls[index]).path[8:]
                    continue
                if requests.get(f'http://img.youtube.com/vi/{self.GetVideoID(urls[index])}/mqdefault.jpg').status_code!=200:
                    logger.warning(f'Youtube Video Not Found: {urls[index]}')
                    error.append(f':warning:[こちらの動画]({urls[index]})は削除または非公開にされています。')
                    urls[index] = None
                    continue
                if self.is_music_premium_video(urls[index]):
                    logger.warning(f'Youtube Music Premium Video: {urls[index]}')
                    error.append(f':warning:[こちらの動画]({urls[index]})はYoutube Music Premiumの動画です。')
                    urls[index] = None
                    continue
                urls[index] = f'https://www.youtube.com/watch?v={self.GetVideoID(urls[index])}'
                continue
            if 'nicovideo' in urls[index]:
                if '?' in urls[index]:
                    urls[index] = urls[index][:urls[index].find('?')]
                    continue
            if 'twitter' in urls[index]:
                if self.GetTweetVideoURL(urls[index]) == "Not Found Video":
                    logger.warning(f'Twitter Video Not Found: {urls[index]}')
                    error.append(f':warning:[こちらのツイート]({urls[index]})から動画を取得できませんでした。')
                    urls[index] = None
                    continue
        # Remove None from urls
        urls = [url for url in urls if url is not None]
        logger.debug(f'Check End URLs: {urls}')
        return urls, error

    def GetVideoID(self, url:str) -> str:
        """
        Get Video ID from URL
        Args:
            url (str): URL

        Returns:
            str: Video ID
            str: 'None' : Failed to get Video ID
        """
        logger.debug(f'Get Video ID from URL: {url}')
        if 't.co' in url or 'x.com' in url:
            url = requests.get(url).url
            logger.debug(f'Convert t.co URL: {url}')
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

    def is_music_premium_video(self, url:str) -> bool:
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

    def GetTweetVideoURL(self, url:str) -> str:
        """Get Tweet Video URL
        Args:
            url (str): URL
        Returns:
            str: Title
        """
        try:
            ydl_opts={
                'skip_download':True,
            }
            with YoutubeDL(ydl_opts) as ydl:
                title=ydl.extract_info(url,download=False)
                print(title["title"])
        except:
            return "Not Found Video"
        else:
            title["title"]
