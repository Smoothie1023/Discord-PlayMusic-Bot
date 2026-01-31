# -*- coding: utf-8 -*-
"""設定管理モジュール"""

import logging
import os
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from typing import Optional

import orjson


@dataclass
class BotConfig:
    """ボット設定"""
    token: str
    guild_id: int
    vc_channel_id: int
    channel_id: int
    interrupt: bool = False


class ConfigManager:
    """設定管理クラス"""

    # パス定数
    DISCORD_TOKEN_FOLDER = '../DiscordTokens/'
    PLAYLIST_PATH = '/Lists/'
    PLAYLIST_DATES_PATH = './data/playlist_date.json'
    LOG_PATH = './Log/PlayAudio.log'
    SETTING_PATH = './Settings/settings.json'

    def __init__(self):
        self.logger = logging.getLogger('PlayAudio')
        self._config: Optional[BotConfig] = None

    def setup_logging(self) -> logging.Logger:
        """ロギングをセットアップ"""
        logger = logging.getLogger('PlayAudio')
        logger.setLevel(logging.DEBUG)

        handler = RotatingFileHandler(
            self.LOG_PATH,
            maxBytes=8*1024*1024,
            backupCount=10,
            encoding='utf-8'
        )
        handler.setLevel(logging.DEBUG)

        fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(fmt)
        logger.addHandler(handler)

        # Discord.pyのログもファイルに出力
        discord_logger = logging.getLogger('discord')
        discord_logger.setLevel(logging.DEBUG)
        discord_logger.addHandler(handler)

        # ログファイルのパーミッション設定
        try:
            os.chmod(self.LOG_PATH, 0o644)
        except Exception:
            pass

        return logger

    def load_tokens(self) -> BotConfig:
        """Discordトークンを読み込み"""
        try:
            with open(os.path.join(self.DISCORD_TOKEN_FOLDER, 'token.txt')) as t, \
                    open(os.path.join(self.DISCORD_TOKEN_FOLDER, 'guild_id.txt')) as g, \
                    open(os.path.join(self.DISCORD_TOKEN_FOLDER, 'vc_channel_id.txt')) as v, \
                    open(os.path.join(self.DISCORD_TOKEN_FOLDER, 'channel_id.txt')) as c:
                token = t.read().strip()
                guild_id = int(g.read().strip())
                vc_channel_id = int(v.read().strip())
                channel_id = int(c.read().strip())

            self._config = BotConfig(
                token=token,
                guild_id=guild_id,
                vc_channel_id=vc_channel_id,
                channel_id=channel_id,
                interrupt=self.load_settings().get('interrupt', False)
            )

            self.logger.info('✅ Discordトークンの読み込みが完了しました')
            return self._config

        except FileNotFoundError as e:
            self.logger.error(f'❌ Discordトークンファイルが見つかりません: {e}')
            self.logger.error('🔧 DiscordTokens/フォルダ内に必要なファイルが存在するか確認してください')
            raise

    def load_settings(self) -> dict:
        """設定ファイルを読み込み"""
        if not os.path.exists(self.SETTING_PATH):
            self.save_settings({'interrupt': False})
            return {'interrupt': False}

        with open(self.SETTING_PATH, 'r') as f:
            settings = orjson.loads(f.read())
            self.logger.info(f'⚙️ 設定の読み込みが完了しました - 割り込み機能: {settings.get("interrupt", False)}')
            return settings

    def save_settings(self, settings: dict):
        """設定ファイルを保存"""
        with open(self.SETTING_PATH, 'w') as f:
            f.write(orjson.dumps(settings, option=orjson.OPT_INDENT_2).decode('utf-8'))

    @property
    def config(self) -> BotConfig:
        """現在の設定を取得"""
        if self._config is None:
            self._config = self.load_tokens()
        return self._config


# グローバルインスタンス
config_manager = ConfigManager()
