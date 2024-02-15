import logging

logger = logging.getLogger('PlayAudio')

class Utils():
    """Utils Class
    Note: This Class is used to manage Utilities
    """
    def __init__(self):
        """Initialize Utils Class"""
        self.logger = logger
        self.logger.info('Utils Class Initialized')

    def delete_space(self,urls:list) -> list:
        """Delete Space
        Note: This Function is used to delete space from URL
        """
        self.logger.info('Call Delete Space')
        for i , url in enumerate(urls):
            url = url.replace(' ','')
            url = url.replace('　','')
            urls[i] = url
            if len(url) == 0:
                urls.pop(i)
        return urls