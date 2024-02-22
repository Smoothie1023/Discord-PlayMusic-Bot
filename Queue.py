from typing import Tuple
import logging

logger = logging.getLogger('PlayAudio')

class Queue:
    """Queue Class
    Note: This Class is used to manage Queue
    """
    def __init__(self):
        """Initialize Queue Class"""
        self.logger = logger
        self.logger.debug('Queue Class Initialized')
        self.queue = []

    def add_queue(self, urls:list) -> Tuple[list, list]:
        """Add Queue
        Note: This Function is used to add Queue
        """
        self.queue.append(list(urls))