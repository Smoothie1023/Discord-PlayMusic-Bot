import os
import logging
import json
import datetime

# Setup Logging
logger = logging.getLogger('PlayAudio')

class Playlist:
    """Playlist Class
    Note: This Class is used to manage Playlist

    Args:
        path (str): Playlist Data Path
        playlist_dates (dict): Playlist Dates
    """
    playlist_dates_path = './playlist_date.json'
    playlist_path = './list/'
    playlist_dates = {}

    def __init__(self):
        """Initialize Playlist Class"""
        self.logger = logger
        self.logger.debug('Playlist Class Initialized')

        if os.path.isfile(self.playlist_dates_path):
            self.playlist_dates = self.load_playlists_date()
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
            self.playlist_dates.update({playlist_name:[]})

    def calculate_playlist_usage(self,file=None) -> list:
        playlist_usage=[]
        self.logger.debug('Calculate Playlist Usage')
        if file == None:
            self.logger.debug('file is None')
            for self.playlist_name in self.playlist_dates:
                usage_count = self.playlist_dates[self.playlist_name]
                playlist_usage.append({self.playlist_name:usage_count})
            sorted_playlists = sorted(playlist_usage, key=lambda x: x[1], reverse=True)
            self.logger.debug(f'Sorted Playlist:{sorted_playlists[:25]}')
            return sorted_playlists[:25]
        else:
            min_playlist_dates = {key: self.playlist_dates[key] for key in self.playlist_dates if key[:-5] in file}
            self.logger.debug(min_playlist_dates)
            for self.playlist_name in min_playlist_dates:
                usage_count = min_playlist_dates[self.playlist_name]
                playlist_usage.append({self.playlist_name:usage_count})
            sorted_playlists = sorted(playlist_usage, key=lambda x: x[1], reverse=True)
            self.logger.debug(f'Sorted Playlist:{sorted_playlists}')
            return sorted_playlists

    def save_playlists_date(self):
        """Save Playlists Date"""
        with open(self.playlist_dates_path, 'w', encoding='utf-8') as f:
            json.dump(self.playlist_dates, f, indent=2, ensure_ascii=False)
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

    def check_file(self, playlist:str) -> bool:
        """Check File"""
        if os.path.isfile(os.path.join(self.playlist_path,f'{playlist}.json')):
            self.logger.debug('File Exists')
            return True
        else:
            self.logger.debug('File Not Found')
            return False