#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import logging
import json
from datetime import datetime

# Setup Logging
logger = logging.getLogger('PlayAudio')

class Playlist:
    """Playlist Class
    Note: This Class is used to manage Playlist

    Args:
        PLAYLIST_PATH (str): Playlist Path
        PLAYLIST_DATES_PATH (str): Playlist Dates Path

    Attributes:
        logger (logging): Logger
        playlist_path (str): Playlist Path
        playlist_dates_path (str): Playlist Dates Path
        playlist_dates (dict): Playlist Dates
    """
    def __init__(self, PLAYLIST_PATH:str ,PLAYLIST_DATES_PATH:str):
        """Initialize Playlist Class"""
        self.logger = logger
        self.logger.debug('Playlist Class Initialized')

        self.playlist_path = PLAYLIST_PATH
        self.logger.debug(f'Playlist Path: {self.playlist_path}')

        self.playlist_dates_path = PLAYLIST_DATES_PATH

        if os.path.isfile(self.playlist_dates_path):
            self.playlist_dates = self.load_playlists_date()
            self.logger.debug(f'Load Playlist Dates: {self.playlist_dates}')
        else:
            self.playlist_dates = {}
            self.save_playlists_date()

    def record_play_date(self,playlist_name:str, play_date:datetime):
        """Record Play Date
        Args:
            playlist_name (str): Playlist Name
            play_date (datetime): Play Date
        """
        play_date=play_date.strftime("%Y-%m-%d %H:%M:%S")
        try:
            if len(self.playlist_dates[playlist_name]) == 0:
                self.playlist_dates[playlist_name].append(play_date)
            else:
                self.playlist_dates[playlist_name][0] = play_date
            self.logger.info(f'Record Date {self.playlist_dates}')
        except KeyError:
            self.logger.warning('KeyError: Playlist Name Not Found')
            self.playlist_dates.update({playlist_name:[play_date]})
            logger.debug(f'Playlist Dates: {self.playlist_dates}')

    def calculate_playlist_usage(self, file:list) -> list:
        """Calculate Playlist Usage
        Args:
            file (list): List of Files
        Returns:
            list: Playlist Usage
        """
        playlist_usage=[]
        self.logger.debug('Calculate Playlist Usage')
        # ファイル名から日付を抽出する辞書
        diff_playlists_dates = {key: self.playlist_dates[key] for key in self.playlist_dates if any(filename in key.split('.')[0] for filename in file)}
        #diff_playlists_dates = {key: self.playlist_dates[key] for key in self.playlist_dates if key in file}
        for playlist_name in diff_playlists_dates:
            usage_count = diff_playlists_dates[playlist_name]
            playlist_usage.append({playlist_name:usage_count})
        try:
            playlist_usage = sorted(playlist_usage, key=lambda x: datetime.strptime(list(x.values())[0][0], '%Y-%m-%d %H:%M:%S') if len(list(x.values())[0]) > 0 else datetime.min, reverse=True)
        except Exception as e:
            logger.error(f'calculate_playlist_usage Error: {e}')
        return playlist_usage[:25]

    def save_playlists_date(self):
        """Save Playlists Date"""
        with open(self.playlist_dates_path, 'w', encoding='utf-8') as f:
            json.dump(self.playlist_dates, f, indent=2, ensure_ascii=False)
            self.logger.info(self.playlist_dates)
            self.logger.info('Save Playlists Date')

    def load_playlists_date(self):
        """Load Playlists Date"""
        with open(self.playlist_dates_path, 'r', encoding='utf-8') as f:
            self.logger.info('Load Playlists Date')
            return json.load(f)

    def delete_playlists_date(self,playlist):
        """Delete Playlists Date

        Args:
            playlist (str): Playlist Name
        """
        del self.playlist_dates[f'{playlist}.json']
        self.logger.info(f'Delete Playlists Date: {playlist}')
        self.save_playlists_date()

    def rename_playlist(self,old_playlist:str, new_playlist:str):
        """Rename Playlists Date
        Args:
            old_playlist (str): Old Playlist Name
            new_playlist (str): New Playlist Name
        """
        self.playlist_dates[f'{new_playlist}.json'] = self.playlist_dates[f'{old_playlist}.json']
        self.delete_playlists_date(old_playlist)
        os.rename(f'{self.playlist_path}{old_playlist}.json', f'{self.playlist_path}{new_playlist}.json')
        self.logger.info(f'Rename Playlists Date: {old_playlist} -> {new_playlist}')
        self.save_playlists_date()

    def check_file(self, playlist:str) -> bool:
        """Check File"""
        if os.path.isfile(os.path.join(self.playlist_path,f'{playlist}.json')):
            self.logger.debug('File Exists')
            return True
        else:
            self.logger.debug('File Not Found')
            return False