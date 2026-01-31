# -*- coding: utf-8 -*-
"""管理コマンド関連のCog"""

import io
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
import orjson

logger = logging.getLogger('PlayAudio')


class AdminCog(commands.Cog):
    """管理機能を提供するCog"""

    def __init__(self, bot: commands.Bot, config, queue, utils, update_manager, music_cog=None):
        self.bot = bot
        self.config = config
        self.queue = queue
        self.utils = utils
        self.update_manager = update_manager
        self.music_cog = music_cog

    def set_music_cog(self, music_cog):
        """MusicCogへの参照を設定"""
        self.music_cog = music_cog

    @app_commands.command(name='reset', description='Botを完全リセットします。')
    async def reset_bot(self, ctx: discord.Interaction):
        """Botを完全リセット"""
        logger.info('=== Bot Complete Reset Started ===')
        await ctx.response.defer()
        reset_steps = []

        try:
            # Step 1: バックグラウンドタスク停止
            logger.info('Step 1: Stopping background tasks...')
            if self.music_cog and self.music_cog.check_music.is_running():
                self.music_cog.check_music.cancel()
                logger.debug('check_music task stopped')
            reset_steps.append('バックグラウンドタスク停止')

            # Step 2: グローバル変数リセット
            logger.info('Step 2: Resetting global variables...')
            if self.music_cog:
                self.music_cog.reset_state()

            # INTERRUPT設定を再読み込み
            try:
                settings = self.config.load_settings()
                self.config._config.interrupt = settings.get('interrupt', False)
                logger.debug(f'INTERRUPT setting reloaded: {self.config._config.interrupt}')
            except Exception as e:
                logger.warning(f'Failed to reload INTERRUPT setting: {e}')

            reset_steps.append('グローバル変数リセット')

            # Step 3: ボイスクライアント切断
            logger.info('Step 4: Disconnecting voice client...')
            vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
            if vc:
                try:
                    if vc.is_playing():
                        vc.stop()
                    vc.cleanup()
                    await vc.disconnect()
                    logger.debug('Voice client disconnected and cleaned up')
                except Exception as e:
                    logger.warning(f'Failed to disconnect voice client: {e}')
            reset_steps.append('ボイスクライアント切断')

            # Step 4: クラスインスタンスリセット
            logger.info('Step 5: Resetting class instances...')
            try:
                self.queue.clear_queue()
                self.queue.now_playing = None
                logger.debug('Queue instance reset')

                # LRUキャッシュクリア
                if hasattr(self.utils, 'get_video_id') and hasattr(self.utils.get_video_id, 'cache_clear'):
                    self.utils.get_video_id.cache_clear()
                if hasattr(self.utils, 'get_title_url') and hasattr(self.utils.get_title_url, 'cache_clear'):
                    self.utils.get_title_url.cache_clear()
                if hasattr(self.utils, 'is_music_premium_video') and hasattr(self.utils.is_music_premium_video, 'cache_clear'):
                    self.utils.is_music_premium_video.cache_clear()
                if hasattr(self.utils, 'get_title_from_ytdlp') and hasattr(self.utils.get_title_from_ytdlp, 'cache_clear'):
                    self.utils.get_title_from_ytdlp.cache_clear()
                logger.debug('Utils LRU cache cleared')

            except Exception as e:
                logger.warning(f'Failed to reset some class instances: {e}')

            reset_steps.append('クラスインスタンスリセット')

            # Step 5: Discordプレゼンスリセット
            logger.info('Step 6: Resetting Discord presence...')
            try:
                await self.bot.change_presence(activity=None)
                logger.debug('Discord presence reset')
            except Exception as e:
                logger.warning(f'Failed to reset Discord presence: {e}')
            reset_steps.append('Discord プレゼンスリセット')

            # Step 6: バックグラウンドタスク再開
            logger.info('Step 7: Restarting background tasks...')
            try:
                if self.music_cog and not self.music_cog.check_music.is_running():
                    self.music_cog.check_music.start()
                    logger.debug('check_music task restarted')
            except Exception as e:
                logger.warning(f'Failed to restart background tasks: {e}')
            reset_steps.append('バックグラウンドタスク再開')

            logger.info('=== Bot Complete Reset Completed Successfully ===')

            embed = discord.Embed(
                title='🔄 完全リセット完了',
                description='Botが初期状態にリセットされました。\n\n✅ 完了した処理:\n' +
                            '\n'.join([f'• {step}' for step in reset_steps]),
                color=0x00ff00
            )
            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.error(f'Reset failed with error: {e}')
            embed = discord.Embed(
                title='⚠️ リセットエラー',
                description=f'リセット中にエラーが発生しました。\n\n完了済み: {len(reset_steps)}個の処理\nエラー内容: {str(e)}',
                color=0xff0000
            )
            await ctx.followup.send(embed=embed)

    @app_commands.command(name='log', description='最新のログファイルを送付します。')
    @app_commands.describe(lines='表示する行数（デフォルト: 50、0で全ファイル）')
    async def log(self, ctx: discord.Interaction, lines: int = 50):
        """ログファイルを送信"""
        log_path = self.config.LOG_PATH

        try:
            if lines == 0:
                await ctx.response.send_message(
                    content='ログファイル全体を出力します。',
                    file=discord.File(log_path)
                )
                return

            with open(log_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

            log_content = ''.join(recent_lines)
            log_file = io.BytesIO(log_content.encode('utf-8'))

            await ctx.response.send_message(
                content=f'最新{len(recent_lines)}行のログを出力します。',
                file=discord.File(log_file, filename=f'PlayAudio_latest_{lines}lines.log')
            )
        except Exception as e:
            logger.error(f'❌ ログファイル送信エラー: {e}')
            await ctx.response.send_message(content=f'ログファイルの送信に失敗しました: {e}')

    @app_commands.command(name='settings', description='設定を変更します。')
    async def setting(self, ctx: discord.Interaction, interrupt: bool):
        """設定を変更"""
        self.config._config.interrupt = interrupt
        self.config.save_settings({'interrupt': interrupt})

        embed = discord.Embed(title='設定を変更しました。', color=0xffffff)
        await ctx.response.send_message(embed=embed)

    @app_commands.command(name='show_setting', description='設定を表示します。')
    async def show_setting(self, ctx: discord.Interaction):
        """設定を表示"""
        settings = self.config.load_settings()

        embed = discord.Embed(title='設定', color=0xffffff)
        embed.add_field(name='曲割り込み機能', value=settings['interrupt'])
        await ctx.response.send_message(embed=embed)

    @app_commands.command(name='update', description='パッケージの更新状況を確認し、更新があれば実行します。')
    @app_commands.default_permissions(administrator=True)
    async def update(self, ctx: discord.Interaction):
        """パッケージを更新"""
        logger.info(f'🔄 /updateコマンドが実行されました - ユーザー: {ctx.user.display_name}')

        await ctx.response.defer()

        updates_available = []
        embed = discord.Embed(title='📦 パッケージ更新チェック中...', color=0x0099ff)

        for package_name in self.update_manager.ALLOWED_PACKAGES:
            try:
                current_version, latest_version, update_available = \
                    await self.update_manager.check_update_available(package_name)

                if current_version and latest_version:
                    if update_available:
                        status = f'🔄 更新可能\n現在: `{current_version}`\n最新: `{latest_version}`'
                        updates_available.append((package_name, current_version, latest_version))
                    else:
                        status = f'✅ 最新\n現在: `{current_version}`'
                    embed.add_field(name=f'{package_name}', value=status, inline=False)
                else:
                    embed.add_field(name=f'{package_name}', value='❌ バージョン情報取得失敗', inline=False)

            except Exception as e:
                logger.error(f'❌ {package_name} 更新チェックエラー: {e}')
                embed.add_field(name=f'{package_name}', value='❌ チェック失敗', inline=False)

        if not updates_available:
            embed.title = '✅ すべてのパッケージが最新です'
            embed.color = 0x00ff00
            await ctx.followup.send(embed=embed)
            return

        embed.title = '🔄 パッケージを更新中...'
        embed.color = 0xff9900
        await ctx.followup.send(embed=embed)

        updated_packages = []
        failed_packages = []

        for package_name, current_ver, latest_ver in updates_available:
            logger.info(f'🔄 {package_name} を更新中: {current_ver} → {latest_ver}')
            success = await self.update_manager.update_package(package_name)

            if success:
                updated_packages.append(package_name)
            else:
                failed_packages.append(package_name)

        if updated_packages:
            result_embed = discord.Embed(
                title='✅ パッケージ更新完了',
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
            await ctx.followup.send(embed=result_embed)

            await self.update_manager.restart_bot()
        else:
            error_embed = discord.Embed(
                title='❌ パッケージ更新に失敗しました',
                description=f'失敗したパッケージ: {", ".join(failed_packages)}',
                color=0xff0000
            )
            await ctx.followup.send(embed=error_embed)


async def setup(bot: commands.Bot):
    """Cogのセットアップ"""
    pass
