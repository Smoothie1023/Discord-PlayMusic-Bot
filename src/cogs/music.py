# -*- coding: utf-8 -*-
"""音楽再生関連のCog"""

import asyncio
import logging
import random
import time
from datetime import datetime
from typing import List, Literal

import discord
from discord import app_commands
from discord.ext import commands, tasks
from niconico import NicoNico
import orjson
import requests

logger = logging.getLogger('PlayAudio')


class MusicCog(commands.Cog):
    """音楽再生機能を提供するCog"""

    def __init__(self, bot: commands.Bot, config, player, queue, playlist, utils):
        self.bot = bot
        self.config = config
        self.player = player
        self.queue = queue
        self.playlist = playlist
        self.utils = utils

        # グローバル状態
        self.nclient = NicoNico()
        self.next_song = None
        self.is_loop = False
        self.current_nvideo = None
        self.current_presence = None

    async def cog_load(self):
        """Cog読み込み時の処理"""
        self.check_music.start()
        logger.info('🔄 音楽監視タスクを開始しました')

    async def cog_unload(self):
        """Cogアンロード時の処理"""
        self.check_music.cancel()

    def play_music(self, vc) -> dict:
        """音楽を再生する

        Args:
            vc (discord.VoiceClient): VoiceClient

        Returns:
            dict: ストリーミング情報
        """
        # ボイス接続確認
        if not vc or not vc.is_connected():
            logger.error('❌ ボイスチャンネルに接続されていません')
            return None

        # キューが空でループもオフの場合は終了
        if (len(self.queue.get_queue()) == 0) and (not self.is_loop):
            return None

        # ループ中なら現在の曲、そうでなければキューから取得
        if self.is_loop:
            url = self.queue.now_playing
        else:
            url = self.queue.pop_queue()

        logger.info(f'🎵 音楽再生を開始します: {url}')

        # 前のニコニコ動画接続をクリーンアップ
        if self.current_nvideo:
            try:
                self.current_nvideo.close()
                logger.debug('🔄 前のニコニコ動画接続を正常にクローズしました')
            except Exception as e:
                logger.warning(f'⚠️ 前のニコニコ動画接続のクローズに失敗しました: {e}')
            finally:
                self.current_nvideo = None

        nvideo = None
        try:
            # ニコニコ動画の場合はダウンロードリンクを取得
            if 'nico' in url:
                nvideo = self.nclient.video.get_video(url)
                nvideo.connect()
                url = nvideo.download_link
                self.current_nvideo = nvideo

            # ストリーミングURL取得
            s_y = self.player.streamming_youtube(url)
            stream_url = s_y.get('url')

            # HLS判定
            is_hls = stream_url and ('.m3u8' in stream_url or s_y.get('protocol') == 'm3u8_native')

            # FFmpegオプション設定
            if is_hls:
                logger.debug('🎵 HLSストリーミングモードで再生します')
                ffmpeg_options = {
                    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -rw_timeout 10000000',
                    'options': '-vn -filter:a loudnorm'
                }
            else:
                logger.debug('🎵 直接ストリーミングモードで再生します')
                ffmpeg_options = {
                    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                    'options': '-vn -filter:a loudnorm'
                }

            log_url = f'{stream_url[:100]}...' if len(stream_url) > 100 else stream_url
            logger.info(f'🎼 音楽ストリーミング開始: {log_url}')
            logger.debug(f'🔧 FFmpegオプション: before={ffmpeg_options["before_options"]}')
            logger.debug(f'🔧 プロトコル: {s_y.get("protocol")}, ext: {s_y.get("ext")}, acodec: {s_y.get("acodec")}')

            audio_source = discord.FFmpegPCMAudio(
                stream_url,
                before_options=ffmpeg_options['before_options'],
                options=ffmpeg_options['options']
            )

            vc.play(
                source=audio_source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._play_next_song(vc, e), self.bot.loop
                )
            )

            logger.debug('✅ 音楽再生の設定が正常に完了しました')
            return s_y

        except Exception as e:
            logger.error(f'❌ 音楽再生処理でエラーが発生しました: {e}')
            if nvideo and nvideo != self.current_nvideo:
                try:
                    nvideo.close()
                    logger.debug('🔄 エラー発生によりニコニコ動画接続をクローズしました')
                except Exception as cleanup_error:
                    logger.warning(f'⚠️ エラー後のニコニコ動画接続クリーンアップに失敗: {cleanup_error}')
            return None

    async def _play_next_song(self, vc, error):
        """曲終了後に次の曲を再生"""
        if error:
            logger.error(f'❌ 音楽再生後のコールバックエラー: {error}')

        try:
            logger.debug('🔄 曲終了検知 - 次の曲の再生準備を開始します')

            if len(self.queue.get_queue()) > 0 or self.is_loop:
                logger.info('🎵 次の曲を自動再生します')
                self.play_music(vc)
            else:
                logger.info('📋 キューが空になりました - 再生を停止します')
                try:
                    channel = self.bot.get_channel(self.config.config.channel_id)
                    if channel:
                        embed = discord.Embed(
                            title='🎵 再生完了',
                            description='キューの再生がすべて終了しました',
                            color=0x00ff00
                        )
                        await channel.send(embed=embed)
                except Exception as channel_error:
                    logger.warning(f'⚠️ 再生完了メッセージ送信エラー: {channel_error}')

        except Exception as e:
            logger.error(f'❌ 次の曲再生準備でエラーが発生しました: {e}')

    def _create_next_embed(self, url: str) -> discord.Embed:
        """次の曲のEmbed作成"""
        try:
            title = self.utils.get_title_url(url)
            if not title:
                title = "タイトル取得中..."

            embed = discord.Embed(
                title='次の曲',
                description=f'[{title}]({url})',
                color=0xffffff
            )
            embed.set_footer(text=f'キューに入っている曲数:{len(self.queue.get_queue())}曲')

            # サムネイル設定
            try:
                if 'youtu' in url:
                    video_id = self.utils.get_video_id(url)
                    if video_id:
                        embed.set_image(url=f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg')
                        logger.debug('🖼️ YouTubeのサムネイル画像を取得しました')
                elif 'nico' in url:
                    video_id = self.utils.get_video_id(url)
                    if video_id:
                        try:
                            with requests.Session() as session:
                                api_url = f'https://ext.nicovideo.jp/api/getthumbinfo/{video_id}'
                                response = session.get(api_url, timeout=5)
                                thumb_url = response.text[
                                    response.text.find('<thumbnail_url>')+15:
                                    response.text.find('</thumbnail_url>')
                                ] + '.L'
                                if session.get(thumb_url, timeout=5).status_code != 200:
                                    thumb_url = thumb_url[:-2]
                                embed.set_image(url=thumb_url)
                                logger.debug('🖼️ ニコニコ動画のサムネイル画像を取得しました')
                        except Exception as nico_error:
                            logger.warning(f'⚠️ ニコニコ動画サムネイル取得エラー: {nico_error}')
            except Exception as thumbnail_error:
                logger.warning(f'⚠️ サムネイル設定でエラー: {thumbnail_error}')

            return embed

        except Exception as e:
            logger.error(f'❌ 次の曲Embed作成でエラー: {e}')
            fallback_embed = discord.Embed(
                title='次の曲',
                description=f'[次の曲]({url})',
                color=0xffffff
            )
            fallback_embed.set_footer(text=f'キューに入っている曲数:{len(self.queue.get_queue())}曲')
            return fallback_embed

    @tasks.loop(seconds=3)
    async def check_music(self) -> None:
        """音楽状態を監視するタスク"""
        await self.bot.wait_until_ready()

        vc_channel = self.bot.get_channel(self.config.config.vc_channel_id)
        channel = self.bot.get_channel(self.config.config.channel_id)

        if not vc_channel or not channel:
            return

        try:
            if not vc_channel.guild.voice_client:
                return

            vc = discord.utils.get(self.bot.voice_clients)
            if vc:
                if vc.is_playing():
                    # プレゼンス更新
                    if self.queue.now_playing:
                        try:
                            title = self.utils.get_title_url(self.queue.now_playing)
                            if title:
                                if self.is_loop:
                                    new_presence = "🔄" + title
                                else:
                                    new_presence = "⏩" + title
                            else:
                                new_presence = "🎵 音楽再生中"
                        except Exception as e:
                            logger.warning(f'⚠️ プレゼンス準備でエラーが発生しました: {e}')
                            new_presence = "🎵 音楽再生中"
                    else:
                        new_presence = "🎵 音楽再生中"

                    if new_presence != self.current_presence:
                        try:
                            await self.bot.change_presence(
                                activity=discord.Activity(
                                    type=discord.ActivityType.listening,
                                    name=new_presence
                                )
                            )
                            self.current_presence = new_presence
                            logger.debug(f'🎵 プレゼンス更新: {new_presence}')
                        except Exception as e:
                            logger.warning(f'⚠️ プレゼンス更新でエラーが発生しました: {e}')

                    # 曲変更検知
                    try:
                        current_source = vc.source
                        if current_source != self.next_song:
                            self.next_song = current_source
                            logger.debug(f'🎵 音楽ソースの変化を検知しました')

                            if len(self.queue.get_queue()) > 0:
                                try:
                                    next_embed = self._create_next_embed(self.queue.get_queue()[0])
                                    await channel.send(embed=next_embed)
                                    logger.info(f'📢 次の曲通知を送信しました')
                                except Exception as embed_error:
                                    logger.warning(f'⚠️ 次の曲Embed作成でエラー: {embed_error}')
                                    simple_embed = discord.Embed(
                                        title='次の曲',
                                        description='次の曲を準備中...',
                                        color=0x00ff00
                                    )
                                    await channel.send(embed=simple_embed)
                    except IndexError:
                        logger.debug('📋 次の曲の通知でIndexError - キューが空です')
                    except Exception as e:
                        logger.warning(f'⚠️ 次の曲の通知でエラーが発生しました: {e}')
                else:
                    if self.current_presence is not None:
                        await self.bot.change_presence(activity=None)
                        self.current_presence = None
                        logger.debug('🎵 プレゼンス更新 - 再生停止')

        except IndexError:
            logger.debug('📋 音楽監視タスクでIndexError')
        except Exception as e:
            logger.error(f'❌ 音楽監視タスクでエラーが発生しました: {e}')

    async def playlist_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """プレイリストのオートコンプリート"""
        import os
        data = []
        playlists = []
        playlist_path = self.config.PLAYLIST_PATH
        files = os.listdir(playlist_path)

        for file in files:
            file = file[:-5]
            if current.lower() in file.lower():
                playlists.append(file)
                if len(data) > 24:
                    break

        playlists = self.playlist.calculate_playlist_usage(playlists)

        for playlist in playlists:
            for file, date in playlist.items():
                file = file[:-5]
                if len(date) == 0:
                    date = ['最後に再生した日付なし']
                if current.lower() in file.lower():
                    data.append(app_commands.Choice(name=file, value=file))

        return data

    @app_commands.command(name='play', description='指定されたURL、プレイリストから曲を再生します。')
    @app_commands.describe(urls='動画のURL', playlists='プレイリスト名', shuffle='シャッフル再生')
    async def play(
        self,
        ctx: discord.Interaction,
        urls: str = None,
        playlists: str = None,
        shuffle: Literal['シャッフル再生'] = None
    ):
        """音楽を再生する"""
        import os

        logger.info(f'🎵 /playコマンドが実行されました - ユーザー: {ctx.user.display_name}')
        logger.debug(f'📝 引数情報 - URLs: {urls}, プレイリスト: {playlists}, シャッフル: {shuffle}')
        start = time.time()

        # ボイスチャンネル接続確認
        if ctx.user.voice is None:
            embed = discord.Embed(title=':warning:ボイスチャンネルに接続してください。', color=0xffffff)
            await ctx.response.send_message(embed=embed)
            logger.warning(f'⚠️ ユーザーがボイスチャンネルに接続していません')
            return

        if urls is None and playlists is None:
            embed = discord.Embed(title=':warning:URLまたはプレイリストを指定してください。', color=0xff0000)
            await ctx.response.send_message(embed=embed)
            return

        await ctx.response.defer()

        if not ctx.guild.voice_client:
            vc = await ctx.user.voice.channel.connect()
            logger.info(f'🔊 ボイスチャンネル "{ctx.user.voice.channel.name}" に接続しました')
            await asyncio.sleep(0.5)

        playlist_path = self.config.PLAYLIST_PATH

        # URL処理
        if urls is not None:
            logger.debug('📋 URL指定モードで処理を開始します')
            urls = urls.split(',')
            urls = self.utils.delete_space(urls)

        # プレイリスト処理
        if playlists is not None:
            playlists = playlists.split(',')
            playlists = self.utils.delete_space(playlists)

            if len(playlists) != len(list(dict.fromkeys(playlists))):
                embed = discord.Embed(title=':warning:重複したプレイリストは削除されました。', color=0xffffff)
                await ctx.channel.send(embed=embed)

            playlists = list(dict.fromkeys(playlists))
            logger.info(f'🗂️ 重複プレイリストを削除しました: {playlists}')

            for playlist in playlists:
                if os.path.exists(f'{playlist_path}{playlist}.json'):
                    self.playlist.record_play_date(f'{playlist}.json', datetime.now())
                    with open(f'{playlist_path}{playlist}.json', 'r', encoding='utf-8') as f:
                        json_list = orjson.loads(f.read())
                        if urls is not None:
                            urls.extend(json_list['urls'])
                        else:
                            urls = json_list['urls']
                else:
                    embed = discord.Embed(title=f':warning:プレイリスト{playlist}が存在しません。', color=0xff0000)
                    await ctx.channel.send(embed=embed)
                    logger.warning(f'Playlist:{playlist} does not exist')

            if urls is None:
                embed = discord.Embed(title=':warning:再生する曲がありません。', color=0xff0000)
                await ctx.followup.send(embed=embed)
                return

            # 重複URL削除
            if len(urls) != len(list(dict.fromkeys(urls))):
                embed = discord.Embed(title=':warning:重複したURLは削除されました。', color=0xffffff)
                await ctx.channel.send(embed=embed)

            urls = list(dict.fromkeys(urls))

        urls, error = self.utils.check_url(urls)
        logger.info(f'URLs: {urls}')

        # エラー処理
        if error:
            embed = discord.Embed(
                title=':warning:以下のエラーが発生しました。',
                description='\n'.join(error),
                color=0xff0000
            )
            await ctx.channel.send(embed=embed)
            logger.error(f'CheckURLErrors: {error}')

            # プレイリスト再生時はエラーURLを自動削除
            if playlists is not None:
                error_urls = []
                for err in error:
                    if '](http' in err:
                        start_idx = err.find('](') + 2
                        end_idx = err.find(')', start_idx)
                        if start_idx > 1 and end_idx > start_idx:
                            error_urls.append(err[start_idx:end_idx])

                if error_urls:
                    total_removed = 0
                    for playlist in playlists:
                        removed = self.playlist.remove_urls_from_playlist(playlist, error_urls)
                        total_removed += removed

                    if total_removed > 0:
                        embed = discord.Embed(
                            title=':wastebasket: エラーURLを自動削除しました',
                            description=f'{total_removed}件のURLをプレイリストから削除しました。',
                            color=0xff9900
                        )
                        await ctx.channel.send(embed=embed)

        if len(urls) == 0:
            embed = discord.Embed(
                title=':warning:無効なURLが指定されました、URLを確認して再度実行してください。',
                color=0xff0000
            )
            await ctx.followup.send(embed=embed)
            return

        # シャッフル
        if shuffle is not None:
            random.shuffle(urls)
            logger.debug('Shuffle URLs')

        # キューに追加
        self.queue.add_queue(urls, interrupt=self.config.config.interrupt)
        logger.debug(f'Queue: {self.queue.get_queue()}')

        # ボイスクライアント取得（再接続対応）
        vc = ctx.guild.voice_client
        if not vc or not vc.is_connected():
            if ctx.user.voice and ctx.user.voice.channel:
                try:
                    vc = await ctx.user.voice.channel.connect()
                    await asyncio.sleep(0.5)
                    logger.info(f'🔊 ボイスチャンネルに再接続しました')
                except Exception as e:
                    logger.error(f'❌ ボイスチャンネル再接続に失敗: {e}')
                    embed = discord.Embed(title=':warning:ボイスチャンネルへの接続に失敗しました。', color=0xff0000)
                    await ctx.followup.send(embed=embed)
                    return
            else:
                embed = discord.Embed(title=':warning:ボイスチャンネルへの接続に失敗しました。', color=0xff0000)
                await ctx.followup.send(embed=embed)
                return

        if not vc.is_playing():
            next_song_url = self.queue.get_queue()[0] if len(self.queue.get_queue()) > 0 else None

            embed = discord.Embed(description='🎵 再生を開始しています...', color=0x00ff00)
            if len(self.queue.get_queue()) != 1:
                embed.set_footer(text=f'他{len(urls)-1}曲はキューに追加しました。')
            await ctx.followup.send(embed=embed)

            self.play_music(vc)

            # 再生開始メッセージ
            try:
                if next_song_url:
                    try:
                        title = self.utils.get_title_url(next_song_url)
                        if title:
                            detailed_embed = discord.Embed(
                                description=f'▶️ [{title}]({next_song_url})を再生開始しました',
                                color=0x00ff00
                            )
                            await ctx.channel.send(embed=detailed_embed)
                            logger.info(f'🎵 再生開始メッセージを送信しました: {title}')
                        else:
                            simple_embed = discord.Embed(
                                description=f'▶️ 再生を開始しました: {next_song_url}',
                                color=0x00ff00
                            )
                            await ctx.channel.send(embed=simple_embed)
                    except Exception as title_error:
                        logger.warning(f'⚠️ タイトル取得でエラー: {title_error}')
                        simple_embed = discord.Embed(
                            description=f'▶️ 再生を開始しました: {next_song_url}',
                            color=0x00ff00
                        )
                        await ctx.channel.send(embed=simple_embed)
            except Exception as e:
                logger.error(f'❌ 再生開始メッセージ処理で予期しないエラー: {e}')

        else:
            embed = discord.Embed(description=f'{len(urls)}曲をキューに追加しました。', color=0xffffff)
            await ctx.followup.send(embed=embed)

        # キュー表示
        if len(urls) <= 5:
            try:
                embed = self.utils.create_queue_embed(
                    urls,
                    title='キューに追加された曲一覧',
                    footer=f'プレイリストに追加された曲数:{len(urls)}曲',
                    addPages=True
                )
                await ctx.channel.send(embed=embed)
            except Exception as e:
                logger.warning(f'⚠️ キュー表示でエラーが発生しました: {e}')
                simple_embed = discord.Embed(
                    title='キューに追加された曲一覧',
                    description=f'{len(urls)}曲が追加されました',
                    color=0x00ff00
                )
                await ctx.channel.send(embed=simple_embed)
        else:
            simple_embed = discord.Embed(
                title='キューに追加された曲一覧',
                description=f'{len(urls)}曲が追加されました\n（曲数が多いため、詳細表示を省略）',
                color=0x00ff00
            )
            await ctx.channel.send(embed=simple_embed)

        # プレイリスト日付保存
        if playlists is not None:
            try:
                for playlist in playlists:
                    self.playlist.record_play_date(f'{playlist}.json', datetime.now())
                self.playlist.save_playlists_date()
            except Exception as e:
                logger.warning(f'⚠️ プレイリスト日付保存でエラーが発生しました: {e}')

        endtime = time.time()
        logger.debug(f'🎵 Playコマンド処理完了時間: {endtime - start:.2f}秒')

    @app_commands.command(name='queue', description='キューの確認')
    async def queue_cmd(self, ctx: discord.Interaction):
        """キューを表示"""
        await ctx.response.defer()

        if self.queue.get_queue():
            logger.debug(f'Queue Sum: {len(self.queue.get_queue())}')

            embed = discord.Embed(
                title='キュー',
                description=f'全{len(self.queue.get_queue())}曲',
                color=0xffffff
            )
            await ctx.followup.send(embed=embed)

            try:
                embed = self.utils.create_queue_embed(
                    self.queue.get_queue(),
                    title='キュー一覧',
                    addPages=True
                )
                await ctx.channel.send(embed=embed)
            except Exception as e:
                logger.warning(f'⚠️ キュー詳細表示でエラー: {e}')
                simple_queue = '\n'.join([
                    f'{i+1}. {url}' for i, url in enumerate(self.queue.get_queue()[:10])
                ])
                fallback_embed = discord.Embed(
                    title='キュー一覧（簡易表示）',
                    description=simple_queue,
                    color=0xffff00
                )
                if len(self.queue.get_queue()) > 10:
                    fallback_embed.set_footer(text=f'他 {len(self.queue.get_queue()) - 10} 曲...')
                await ctx.channel.send(embed=fallback_embed)
        else:
            embed = discord.Embed(title=':warning:キューに曲が入っていません。', color=0xffff00)
            await ctx.followup.send(embed=embed)

    @app_commands.command(name='skip', description='現在の曲をスキップします。')
    async def skip(self, ctx: discord.Interaction, index: int = None):
        """曲をスキップ"""
        logger.info(f'⏭️ /skipコマンドが実行されました - ユーザー: {ctx.user.display_name}, インデックス: {index}')

        if ctx.user.voice is None:
            embed = discord.Embed(title=':warning:ボイスチャンネルに接続してください。', color=0xff0000)
            await ctx.response.send_message(embed=embed)
            return

        if index is not None:
            if index < 1:
                embed = discord.Embed(title=':warning:1曲未満をスキップすることはできません。', color=0xff0000)
                await ctx.response.send_message(embed=embed)
                return
            index = index - 1
        else:
            index = 0

        vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        # ニコニコ動画接続クリーンアップ
        if self.current_nvideo:
            try:
                self.current_nvideo.close()
                logger.debug('🔄 スキップによりニコニコ動画接続をクローズしました')
            except Exception as e:
                logger.warning(f'⚠️ スキップ時のニコニコ動画接続クローズに失敗: {e}')
            finally:
                self.current_nvideo = None

        if vc and vc.is_playing():
            if self.is_loop:
                self.is_loop = False
                embed = discord.Embed(title='ループ再生を解除しました。', color=0xffffff)
                await ctx.channel.send(embed=embed)

            self.queue.skip_queue(index)

            if len(self.queue.get_queue()) == 0:
                embed = discord.Embed(title=':warning:キューに曲がありません。', color=0xffff00)
                await ctx.response.send_message(embed=embed)
                vc.stop()
                return

            embed = discord.Embed(
                title=f'{index+1}曲をスキップしました。',
                description=f'[{self.utils.get_title_url(self.queue.get_queue()[0])}]({self.queue.get_queue()[0]})を再生します。',
                color=0xffffff
            )
            await ctx.response.send_message(embed=embed)
            vc.stop()
        else:
            embed = discord.Embed(title=':warning:再生中の曲がありません。', color=0xffff00)
            await ctx.response.send_message(embed=embed)

    @app_commands.command(name='loop', description='ループの設定')
    async def loop(self, ctx: discord.Interaction):
        """ループ設定の切り替え"""
        vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        if vc and vc.is_playing():
            if self.is_loop:
                self.is_loop = False
                embed = discord.Embed(title='ループ再生を解除しました。', color=0xffffff)
                logger.debug('Loop is False')
            else:
                self.is_loop = True
                embed = discord.Embed(title='ループ再生を設定しました。', color=0xffffff)
                logger.debug('Loop is True')
            await ctx.response.send_message(embed=embed)
        else:
            embed = discord.Embed(title=':warning:再生中の曲がありません。', color=0xffff00)
            await ctx.response.send_message(embed=embed)

    def reset_state(self):
        """状態をリセット"""
        self.next_song = None
        self.is_loop = False
        self.current_presence = None

        if self.current_nvideo:
            try:
                self.current_nvideo.close()
            except Exception as e:
                logger.warning(f'Failed to close NVIDEO on reset: {e}')
            finally:
                self.current_nvideo = None


async def setup(bot: commands.Bot):
    """Cogのセットアップ（引数は後からbotに設定）"""
    pass
