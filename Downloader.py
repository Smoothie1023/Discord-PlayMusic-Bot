import logging
import json
import urllib.request
from urllib.parse import urlparse, parse_qs
import re
import requests

from yt_dlp import YoutubeDL
from niconico import NicoNico

# Setup Logging
logger = logging.getLogger('PlayAudio')
# Initialize NicoNico
Nclient = NicoNico()

class Downloader:
    """Download from URL Class
    Note: This Class is used to download from URL
    """

    # YoutubeDL Options Default
    ydl_opts_default = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '96'
        }],
    }
    # YoutubeDL Options Only Info
    ydl_opts_only_info = {
        'skip_download': True
    }

    def __init__(self):
        """Initialize Downloader Class"""
        self.logger = logger
        self.logger.debug('Downloader Class Initialized')

    def streamming_youtubedl(self, url:str,options:list = ydl_opts_default) -> dict:
        """Streamming from YoutubeDL
        Note: This Function is used to get streamming Video from YoutubeDL

        Args:
            url (str): URL

        Returns:
            dict: Streamming Information
        """
        self.logger.debug(f'YoutubeDL Streamming URL: {url}')
        self.logger.debug(f'YoutubeDL Streamming Options: {options}')
        if 'nico' in url:
            nvideo = Nclient.video.get_video(url)
            nvideo.connect()
            url=nvideo.download_link
            self.logger.debug(f'NicoNico Streamming URL: {url}')

        with YoutubeDL(options) as ydl:
            song = ydl.extract_info(url, download=False)
            self.logger.info(f'YoutubeDL Streamming Information: {song}')
        return song

    def get_info(self, source_url:str, options:str) -> str:
        """Get Info from URL
        Note: This Function is used to get info from URL

        Args:
            source_url (str): source_url
            options (str): 'title' or 'thumbnail'

        Returns:
            str: Title : Select Options 'title'
            str: Thumbnail : Select Options 'thumbnail'
            None: Failed to get info
        """
        self.logger.info(f'Get Title from URL: {source_url}')

        if 'youtu' in source_url:
            params = {'format': 'json', 'url': source_url}
            url = 'https://www.youtube.com/oembed'
            query_string = urllib.parse.urlencode(params)
            url = url + '?' + query_string
            self.logger.debug(f'URL: {url}')
            try:
                with urllib.request.urlopen(url) as response:
                    response_text = response.read()
                    data = json.loads(response_text.decode())
                    if(options == 'title'):
                        title = data['title']
                        self.logger.info(f'Title: {title}')
                        return title
                    elif (options == 'thumbnail'):
                        thumbnail = data['thumbnail_url']
                        self.logger.info(f'Thumbnail: {thumbnail}')
                        return thumbnail
                    else:
                        self.logger.warning('Not Supported Options')
                        return None
            except urllib.error.HTTPError as e:
                self.logger.error(f'urllib.error.HTTPError Exception: {e}')
                try:
                    info = self.streamming_youtubedl(source_url, self.ydl_opts_only_info)
                    self.logger.debug(f'Info: {info}')
                except Exception as e:
                    self.logger.error(f'streamming_youtubedl Exception: {e}')
                    return None
                if(options == 'title'):
                    title = info['title']
                    self.logger.info(f'Title: {title}')
                    return title
                elif (options == 'thumbnail'):
                    thumbnail = info['thumbnail']
                    self.logger.info(f'Thumbnail: {thumbnail}')
                    return thumbnail
                else:
                    self.logger.warning('Not Supported Options')
                    return None
            except Exception as e:
                self.logger.critical(f'Exception: {e}')
                return None
        elif 'nico' in source_url:
            url=f"https://ext.nicovideo.jp/api/getthumbinfo/{self.GetVideoID(source_url)}"
            res=requests.get(url)
            return res.text[res.text.find("<title>")+7:res.text.rfind("</title>")]

    def GetVideoID(self,url:str) -> str:
        """Get Video ID from URL

        Args:
            url (str): URL

        Returns:
            str: Video ID
            str: 'None' : Failed to get Video ID
        """
        self.logger.info(f'Get Video ID from URL: {url}')
        if 't.co' in url:
            url=requests.get(url).url
            self.logger.debug(f'Convert t.co URL: {url}')
        if 'youtu.be' in url:
            result = urlparse(url).path
            self.logger.debug(f'Youtube.be Video ID: {result[1:]}')
            return result[1:]
        elif 'youtube' in url:
            if 'live' in url:
                result = urlparse(url).path
                self.logger.debug(f'Youtube Live Video ID: {result[6:]}')
                return result[6:]
            result = urlparse(url).path
            result = parse_qs(result)['v'][0]
            self.logger.debug(f'Youtube Video ID: {result}')
            return result
        elif 'nico' in url:
            pattern=re.compile(r'(sm|nm)(\d)*')
            self.logger.debug(f'NicoNico Video ID: {pattern.search(url).group()}')
            return pattern.search(url).group()
        elif 'twitter' in url:
            if '/video' in url:
                result = url[url.rfind('status/')+7:url.rfind('/video')]
                self.logger.debug(f'Twitter Video ID: {result}')
                return result
        else:
            self.logger.warning('Can\'t Get Video ID')
            return 'None'