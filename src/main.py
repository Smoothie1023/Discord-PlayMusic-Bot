# -*- coding: utf-8 -*-
"""
PlayAudio Discord Bot - エントリーポイント

このファイルはボットの起動とCogの読み込みを行うシンプルなエントリーポイントです。
各機能は以下のCogに分割されています：
- cogs/music.py: 音楽再生機能（play, queue, skip, loop）
- cogs/playlist.py: プレイリスト管理機能
- cogs/admin.py: 管理機能（reset, log, settings, update）
"""

import asyncio
import logging

import discord
from discord.ext import commands

# 各モジュールのインポート
from config import config_manager
import Downloader as DownloaderModule
import Player as PlayerModule
import Playlist as PlaylistModule
import Queue as QueueModule
import UpdateManager as UpdateManagerModule
import Utils as UtilsModule

# Cogsのインポート
from cogs.music import MusicCog
from cogs.playlist import PlaylistCog
from cogs.admin import AdminCog

# ログ設定
logger = config_manager.setup_logging()
logger.info('📢 PlayAudio Bot を開始しています...')

# Discord設定読み込み
try:
    bot_config = config_manager.load_tokens()
    GUILD = discord.Object(bot_config.guild_id)
except FileNotFoundError:
    exit(1)

# 各クラスのインスタンス化
Downloader = DownloaderModule.Downloader()
Player = PlayerModule.Player()
Playlist = PlaylistModule.Playlist(config_manager.PLAYLIST_PATH, config_manager.PLAYLIST_DATES_PATH)
Queue = QueueModule.Queue()
Utils = UtilsModule.Utils()
UpdateManager = UpdateManagerModule.UpdateManager()


class PlayAudioBot(commands.Bot):
    """PlayAudio Discord Bot"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True

        super().__init__(
            command_prefix='!',
            intents=intents,
        )

        self.config_manager = config_manager
        self.guild = GUILD

        # Cogインスタンスを保持
        self.music_cog = None
        self.playlist_cog = None
        self.admin_cog = None

    async def setup_hook(self):
        """Cog読み込みとコマンド同期"""
        # Cogの作成と追加
        self.music_cog = MusicCog(
            self,
            config_manager,
            Player,
            Queue,
            Playlist,
            Utils
        )
        self.playlist_cog = PlaylistCog(
            self,
            config_manager,
            Playlist,
            Utils
        )
        self.admin_cog = AdminCog(
            self,
            config_manager,
            Queue,
            Utils,
            UpdateManager,
            self.music_cog
        )

        await self.add_cog(self.music_cog)
        await self.add_cog(self.playlist_cog)
        await self.add_cog(self.admin_cog)

        # オートコンプリートの設定
        self._setup_autocomplete()

        # コマンド同期
        self.tree.copy_global_to(guild=self.guild)
        await self.tree.sync(guild=self.guild)
        logger.info('✅ Discordスラッシュコマンドの同期が完了しました')

    def _setup_autocomplete(self):
        """オートコンプリートを設定"""
        # MusicCogのplayコマンドにオートコンプリートを追加
        play_cmd = self.tree.get_command('play', guild=self.guild)
        if play_cmd:
            play_cmd.autocomplete('playlists')(self.music_cog.playlist_autocomplete)

        # PlaylistCogのコマンドにオートコンプリートを追加
        playlist_commands = [
            'プレイリストに曲を追加',
            'プレイリストを削除',
            'プレイリストから曲を削除',
            'プレイリスト名を変更',
            'プレイリストに登録されている曲を表示',
            'プレイリストのロックを変更',
        ]

        for cmd_name in playlist_commands:
            cmd = self.tree.get_command(cmd_name, guild=self.guild)
            if cmd:
                cmd.autocomplete('playlist')(self.playlist_cog.playlist_autocomplete)

        # プレイリスト結合コマンドのオートコンプリート
        join_cmd = self.tree.get_command('プレイリストを結合する', guild=self.guild)
        if join_cmd:
            join_cmd.autocomplete('parent_playlist')(self.playlist_cog.playlist_autocomplete)
            join_cmd.autocomplete('child_playlist')(self.playlist_cog.playlist_autocomplete)

    async def on_ready(self):
        """ボット起動完了時"""
        logger.info('🚀 Discord Bot が正常に起動しました')
        logger.info(f'👤 ログイン名: {self.user.name}#{self.user.discriminator}')

        guild = self.get_guild(bot_config.guild_id)
        if guild:
            logger.info(f'🏠 接続サーバー: {guild.name}')
        else:
            logger.warning(
                f'⚠️ ギルドID {bot_config.guild_id} が見つかりません。'
                'ボットがサーバーに参加しているか確認してください。'
            )

        # 起動時の自動更新チェック
        await self._auto_update_on_startup(guild)

    async def _auto_update_on_startup(self, guild):
        """起動時に自動でパッケージ更新をチェック・実行"""
        logger.info('🔍 起動時の自動更新チェックを開始します...')

        updates_available = []

        for package_name in UpdateManager.ALLOWED_PACKAGES:
            try:
                current_version, latest_version, update_available = \
                    await UpdateManager.check_update_available(package_name)

                if update_available and current_version and latest_version:
                    updates_available.append((package_name, current_version, latest_version))
                    logger.info(f'📦 {package_name} の更新が利用可能: {current_version} → {latest_version}')

            except Exception as e:
                logger.error(f'❌ {package_name} 自動更新チェックエラー: {e}')

        if not updates_available:
            logger.info('✅ すべてのパッケージが最新です')
            return

        # 更新通知をDiscordに送信
        channel = self.get_channel(bot_config.channel_id)
        if channel:
            embed = discord.Embed(
                title='🔄 パッケージ更新を検出しました',
                description='自動更新を実行します...',
                color=0xff9900
            )
            for package_name, current_ver, latest_ver in updates_available:
                embed.add_field(
                    name=package_name,
                    value=f'`{current_ver}` → `{latest_ver}`',
                    inline=False
                )
            await channel.send(embed=embed)

        # 更新を実行
        updated_packages = []
        failed_packages = []

        for package_name, current_ver, latest_ver in updates_available:
            logger.info(f'🔄 {package_name} を自動更新中: {current_ver} → {latest_ver}')
            success = await UpdateManager.update_package(package_name)

            if success:
                updated_packages.append(package_name)
            else:
                failed_packages.append(package_name)

        # 結果を通知
        if channel:
            if updated_packages:
                result_embed = discord.Embed(
                    title='✅ 自動更新完了',
                    description=f'更新されたパッケージ: {", ".join(updated_packages)}',
                    color=0x00ff00
                )
                if failed_packages:
                    result_embed.add_field(
                        name='❌ 更新失敗',
                        value=', '.join(failed_packages),
                        inline=False
                    )
                result_embed.add_field(
                    name='🔄 再起動',
                    value='Botを再起動します...',
                    inline=False
                )
                await channel.send(embed=result_embed)
            else:
                error_embed = discord.Embed(
                    title='❌ 自動更新に失敗しました',
                    description=f'失敗したパッケージ: {", ".join(failed_packages)}',
                    color=0xff0000
                )
                await channel.send(embed=error_embed)

        # 更新があった場合は再起動
        if updated_packages:
            await UpdateManager.restart_bot()

    async def on_voice_state_update(self, member, before, after):
        """ボイスチャンネル状態更新時の処理"""
        voice_state = member.guild.voice_client

        if voice_state is not None and len(voice_state.channel.members) == 1:
            voice_state.cleanup()

            # MusicCogの状態をリセット
            if self.music_cog:
                self.music_cog.reset_state()

            Queue.clear_queue()
            await self.change_presence(activity=None)
            await voice_state.disconnect()

    async def on_app_command_error(self, interaction: discord.Interaction, error):
        """アプリケーションコマンドエラー処理"""
        logger.critical(f'🚨 アプリケーションコマンドでクリティカルエラーが発生しました: {error}')
        logger.error(
            f'📍 エラー発生場所 - コマンド: {interaction.command.name if interaction.command else "不明"}, '
            f'ユーザー: {interaction.user.display_name}'
        )

        embed = discord.Embed(
            title=f'🚨 重大なエラーが発生しました: {error}',
            color=0xff0000
        )
        await interaction.channel.send(embed=embed)


def main():
    """メイン関数"""
    bot = PlayAudioBot()
    bot.run(bot_config.token)


if __name__ == '__main__':
    main()
