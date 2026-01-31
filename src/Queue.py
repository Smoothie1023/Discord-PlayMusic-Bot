# -*- coding: utf-8 -*-
import logging

logger = logging.getLogger('PlayAudio')


class Queue:
    """Queue Class
    Note: This Class is used to manage Queue
    """
    def __init__(self):
        """Initialize Queue Class"""
        self.logger = logger
        self.logger.debug('📋 Queue クラスが初期化されました')
        self.queue = []
        self.now_playing = None

    def add_queue(self, urls: list, interrupt: bool) -> list:
        """Add Queue
        Note: This Function is used to add Queue

        Args:
            urls (list): List of URLs

        Returns:
            list: List of URLs

        """
        if interrupt:
            tmp = self.queue.copy()
            self.queue.clear()
            self.queue.extend(list(urls))
            self.queue.extend(tmp)
        else:
            self.queue.extend(list(urls))
        self.logger.info(f'📋 キューに追加完了 - 割り込み: {interrupt}, 現在のキュー長: {len(self.queue)}曲')
        return self.queue

    def clear_queue(self) -> list:
        """Clear Queue
        Note: This Function is used to clear Queue

        Returns:
            list: List of URLs
        """
        self.queue = []
        self.logger.info('🗑️ キューをクリアしました')
        return self.queue

    def skip_queue(self, index: int) -> None:
        """Skip Queue
        Note: This Function is used to skip Queue

        Args:
            index (int): Index of Queue

        """
        if index < len(self.queue):
            self.queue = self.queue[index:]
            self.logger.info(f'⏭️ キューを{index}曲スキップしました - 残りキュー長: {len(self.queue)}曲')
        else:
            self.queue.clear()
            self.logger.info('⏭️ キューを全てスキップしました（キューが空になりました）')

    def get_queue(self) -> list:
        """Get Queue
        Note: This Function is used to get Queue

        Returns:
            list: List of URLs
        """
        self.logger.debug(f'📋 キュー情報取得 - 現在のキュー長: {len(self.queue)}曲')
        return self.queue

    def pop_queue(self) -> str:
        """Pop Queue
        Note: This Function is used to pop Queue

        Returns:
            str: URL
        """
        url = self.queue.pop(0)
        self.now_playing = url
        self.logger.info(f'🎵 キューから次の曲を取得しました - 残りキュー長: {len(self.queue)}曲')
        self.logger.debug(f'▶️ 再生開始: {url}')
        return url
