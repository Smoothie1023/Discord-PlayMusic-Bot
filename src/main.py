#!/usr/bin/env python3
import json
import logging
import os
import random
import time
from collections import deque
from datetime import datetime
from typing import List, Literal
import urllib.request
from urllib.parse import urlparse, parse_qs

import discord
from discord import app_commands
from discord.ext import tasks
from discord.ui import Modal, View, text_input
from bs4 import BeautifulSoup
from niconico import NicoNico
import requests
from yt_dlp import YoutubeDL

import Downloader as Downloader
import Player
import Playlist
import Queue
import Utils

# Setup Logging
logger = logging.getLogger('PlayAudio')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('Log/PlayAudio.log', encoding='utf-8')
logger.addHandler(handler)
fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(fmt)

logger.info('Starting PlayAudio')

#Global Variables
global NEXT_SONG
global IS_LOOP
# Constants
# Discord Bot Initialize
client = discord.Client(intents = discord.Intents.default())
tree = discord.app_commands.CommandTree(client)
NCLIENT = NicoNico()
NEXT_SONG = None
IS_LOOP = False
# PlayList Path
PLAYLIST_PATH = 'lists/'
# PlayList Dates Path
PLAYLIST_DATES_PATH = './playlist_date.json'

# Discord Token Folder Path
DISCORD_TOKEN_FOLDER_PATH = 'DiscordTokens/'
# Load Discord Tokens
with open(os.path.join(DISCORD_TOKEN_FOLDER_PATH, 'token.txt')) as t, \
    open(os.path.join(DISCORD_TOKEN_FOLDER_PATH, 'guild_id.txt')) as g, \
    open(os.path.join(DISCORD_TOKEN_FOLDER_PATH, 'vc_channel_id.txt')) as v, \
    open(os.path.join(DISCORD_TOKEN_FOLDER_PATH, 'channel_id.txt')) as c:
        TOKEN = t.read()
        GUILD_ID = g.read()
        VC_CHANNEL_ID = int(v.read())
        CHANNEL_ID = int(c.read())
        GUILD = discord.Object(GUILD_ID)

logger.info('Discord Token Loaded')

# Downloader Initialize
Downloader = Downloader.Downloader()
# Player Initialize
Player = Player.Player()
# Playlist Initialize
Playlist = Playlist.Playlist(PLAYLIST_PATH, PLAYLIST_DATES_PATH)
# Queue Initialize
Queue = Queue.Queue()
# Utils Initialize
Utils = Utils.Utils()

# Youtube Streamming Function
def play_music(vc) -> dict:
    """Play Music Function
    Args:
        vc (discord.VoiceClient): VoiceClient

    Returns:
        dict: Streamming URL
    """
    global IS_LOOP
    # Check if Queue is empty and Loop is False
    if (len(Queue.get_queue()) == 0) and (not IS_LOOP):
        return
    # Check if Loop
    if IS_LOOP:
        url = Queue.now_playing
    else:
        url = Queue.pop_queue()
    logger.info(f'Play Music: {url}')
    # Close NVideo
    try:
        NVIDEO.close()
        logger.info('Closed NVideo')
    except:
        pass
    # if niconico video get download link
    if 'nico' in url:
        try:
            NVIDEO = NCLIENT.video.get_video(url)
            NVIDEO.connect()
            url = NVIDEO.download_link
        except:
            pass
    # get streamming url
    s_y = Player.streamming_youtube(url)

    # ffmpeg options
    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a loudnorm'}
    try:
        logger.info(f'Stremming Music URL: {s_y["url"]}')
        vc.play(source=discord.FFmpegPCMAudio(s_y["url"],**ffmpeg_options),after=lambda e:play_music(vc))
    except Exception as e:
        logger.error(f'play_music_Error: {e}')
        return
    return s_y

# Notificate change Music
@tasks.loop(seconds=1)
async def check_music() -> None:
    """Notificate change Music"""
    global NEXT_SONG, IS_LOOP
    # Wait run Bot
    await client.wait_until_ready()
    vc_channel = client.get_channel(VC_CHANNEL_ID)
    channel = client.get_channel(CHANNEL_ID)

    try:
        if vc_channel.guild.voice_client:
            vc = discord.utils.get(client.voice_clients)
            if vc.is_playing():
                # Change Presence
                if IS_LOOP:
                    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="🔄"+Utils.get_title_url(Queue.now_playing)))
                else:
                    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="⏩"+Utils.get_title_url(Queue.now_playing)))

                # Check if Next Song
                if vc.source is None:
                    NEXT_SONG = vc.source
                    await channel.send(embed=create_next_embed(Queue.get_queue()[0]))
                if vc.source != NEXT_SONG:
                    NEXT_SONG = vc.source
                    await channel.send(embed=create_next_embed(Queue.get_queue()[0]))
            else:
                await client.change_presence(activity=None)
    except IndexError:
        pass
    except Exception as e:
        logger.error(f'tasks.loop_Error: {e}')

# Create Next Embed
def create_next_embed(url:str):
    """Create Next Embed
    Args:
        url (str): URL
    Returns:
        discord.Embed: Embed
    """
    embed=discord.Embed(title='次の曲', description=f'[{Utils.get_title_url(url)}]({url})', color=0xffffff)
    if 'youtu' in url:
        embed.set_image(url=f'https://img.youtube.com/vi/{Utils.get_video_id(url)}/mqdefault.jpg')
        logger.info('Get Youtube thumbnail')
    elif 'nico' in url:
        with requests.Session() as session:
            url=f'https://ext.nicovideo.jp/api/getthumbinfo/{Utils.get_video_id(url)}'
            url=session.get(url)
            url=url.text[url.text.find('<thumbnail_url>')+15:url.text.find('</thumbnail_url>')]+'.L'
            if session.get(url).status_code!=200:
                url=url[:-2]
            embed.set_image(url=url)
            logger.info('Get niconico thumbnail')
    else:
        logger.info('Can\'t Get thumbnail')
    logger.info(f'thumbnailURL:{url}')
    return embed

# AutoComplete Playlist
async def playlist_autocomplete(
    interaction:discord.Interaction,
    current:str
    )->List[app_commands.Choice[str]]:
    """AutoComplete Playlist
    Args:
        interaction (discord.Interaction): Interaction
        current (str): Current
    Returns:
        List[app_commands.Choice[str]]: Playlist
    """
    data = []
    playlists = []
    files = os.listdir(PLAYLIST_PATH)
    logger.debug(f'Playlist Files: {files}')
    for file in files:
        file = file[:-5]
        if current.lower() in file.lower():
            #data.append(app_commands.Choice(name = file, value = file))
            playlists.append(file)
            if len(data) > 24:
                break
    logger.debug(f'Playlist Data: {data}')
    playlists = Playlist.calculate_playlist_usage(playlists)
    logger.debug(f'Playlist: {playlists}')
    for playlist in playlists:
        for file, date in playlist.items():
            file = file[:-5]
            if len(date) == 0:
                date=['最後に再生した日付なし']
            if current.lower() in file.lower():
                data.append(app_commands.Choice(name = file, value = file))
    logger.debug(f'Playlist Data: {data}')
    return data

# Delete Playlist Input Modal
class DeleteInput(Modal, title = 'プレイリストを削除'):
    text = text_input.TextInput(label = '削除するプレイリスト名', placeholder = 'プレイリスト名', max_length = 100, required = True)
    def __init__(self, playlist:str):
        super().__init__(title = '⚠削除後復元はできません！')
        self.playlist = playlist

    async def on_submit(self, interaction:discord.Interaction):
        if self.text.value == self.playlist:
            os.remove(f'{PLAYLIST_PATH}{self.playlist}.json')
            embed = discord.Embed(title = f'プレイリスト:{self.playlist}を削除しました。', color = 0xffffff)
            Playlist.delete_playlists_date(self.playlist)
            await interaction.response.send_message(embed = embed)
            logger.info(f'Delete Playlist: {self.playlist}')
        else:
            embed = discord.Embed(title = ':warning:プレイリスト名が一致しません。', color = 0xffff00)
            await interaction.response.send_message(embed = embed)
            logger.warning('Playlist Name does not match')

    async def on_cancel(self, interaction:discord.Interaction):
        embed = discord.Embed(title = 'プレイリスト削除をキャンセルしました。', color = 0xffffff)
        await interaction.response.send_message(embed = embed)
        logger.info('Cancel Delete Playlist')

    async def on_timeout(self):
        embed = discord.Embed(title = 'プレイリスト削除をキャンセルしました。', color = 0xffffff)
        await self.message.edit(embed = embed)
        logger.info('Timeout Delete Playlist')

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        return await interaction.response.send_message(error)

# Discord Bot Commands
# Play Command
@tree.command(
    guild = GUILD,
    name = 'play',
    description = '指定されたURL、プレイリストから曲を再生します。'
)
@discord.app_commands.describe(
    urls = '動画のURL',
    playlists = 'プレイリスト名',
    shuffle = 'シャッフル再生'
)
@app_commands.autocomplete(playlists = playlist_autocomplete)
async def play(ctx:discord.Interaction, urls:str = None, playlists:str = None,
                shuffle:Literal['シャッフル再生'] = None):
    logger.debug('Play Command')
    logger.debug(f'User: {ctx.user}')
    logger.debug('args')
    logger.debug(f'URLs: {urls}')
    logger.debug(f'Playlists: {playlists}')
    logger.debug(f'Shuffle: {shuffle}')
    # Set Start Time for Debugging
    start = time.time()

    # Check if User is connected to Voice Channel
    if ctx.user.voice is None:
        embed = discord.Embed(title = ':warning:ボイスチャンネルに接続してください。', color = 0xffffff)
        await ctx.response.send_message(embed=embed)
        logger.warning('User is not connected to Voice Channel')
        return

    if urls is None and playlists is None:
        embed = discord.Embed(title = ':warning:URLまたはプレイリストを指定してください。', color = 0xff0000)
        await ctx.response.send_message(embed=embed)
        logger.warning('No URL or Playlist')
        return

    await ctx.response.defer()

    # Select URL Option
    if urls is not None:
        logger.debug('URL is not None')
        urls = urls.split(',')
        urls = Utils.delete_space(urls)

    # Select Playlist Option
    if playlists is not None:
        playlists = playlists.split(',')
        # Delete Duplicate Playlists
        playlists = Utils.delete_space(playlists)
        if len(playlists) != len(list(dict.fromkeys(playlists))):
            embed = discord.Embed(title = ':warning:重複したプレイリストは削除されました。', color = 0xffffff)
            await ctx.channel.send(embed = embed)
        playlists = list(dict.fromkeys(playlists))
        logger.info(f'Delete Duplicate Playlists: {playlists}')

        # Get URLs from Playlists
        for playlist in playlists:
            if os.path.exists(f'{PLAYLIST_PATH}{playlist}.json'):
                Playlist.record_play_date(f'{playlist}.json',datetime.now())
                with open(f'{PLAYLIST_PATH}{playlist}.json','r',encoding='utf-8') as f:
                    json_list = json.load(f)
                    if urls is not None:
                        urls.extend(json_list['urls'])
                    else:
                        urls = json_list['urls']
            else:
                embed = discord.Embed(title = f':warning:プレイリスト{playlist}が存在しません。', color = 0xff0000)
                await ctx.channel.send(embed = embed)
                logger.warning(f'Playlist:{playlist} does not exist')

        if urls is None:
            embed = discord.Embed(title = ':warning:再生する曲がありません。', color = 0xff0000)
            await ctx.followup.send(embed = embed)
            logger.warning('No music to play command')
            return

        # Delete Duplicate URLs
        if len(urls) != len(list(dict.fromkeys(urls))):
            embed = discord.Embed(title = ':warning:重複したURLは削除されました。', color = 0xffffff)
            await ctx.channel.send(embed = embed)
        urls = list(dict.fromkeys(urls))
        urls, error = Utils.check_url(urls)
        logger.info(f'URLs: {urls}')

        # Check if Error Occurred
        if error:
            embed = discord.Embed(title = ':warning:以下のエラーが発生しました。', description = '\n'.join(error), color = 0xff0000)
            await ctx.channel.send(embed = embed)
            logger.error(f'CheckURLErrors: {error}')

        # Check if URL does not exist
        if len(urls) == 0:
            embed = discord.Embed(title = ':warning:無効なURLが指定されました、URLを確認して再度実行してください。', color = 0xff0000)
            await ctx.followup.send(embed = embed)
            logger.warning('URL does not exist')
            return

    if not ctx.guild.voice_client:
        # Connect to Voice Channel
        await ctx.user.voice.channel.connect()
        logger.debug('Connected to Voice Channel')

    # if shuffle is not None shuffle urls
    if shuffle is not None:
        random.shuffle(urls)
        logger.debug('Shuffle URLs')

    # add url to queue
    Queue.add_queue(urls)
    logger.debug('Add URLs to Queue')
    logger.debug(f'Queue: {Queue.get_queue()}')

    vc = discord.utils.get(client.voice_clients,guild=ctx.guild)

    if not vc.is_playing():
        embed = discord.Embed(description = f'[{Utils.get_title_url(Queue.get_queue()[0])}]({Queue.get_queue()[0]})を再生します。', color = 0xffffff)
        if len(Queue.get_queue()) != 1:
            embed.set_footer(text=f'他{len(urls)-1}曲はキューに追加しました。')
        await ctx.followup.send(embed = embed)
        play_music(vc)
    else:
        embed = discord.Embed(description = f'{len(urls)}曲をキューに追加しました。', color = 0xffffff)
        await ctx.followup.send(embed = embed)

        # Show Queue
        PAGES = len(Utils.chunk_list(urls, 10))
        for i in range(PAGES):
            queue_slice = urls[i*10:(i+1)*10]
            queue_description = '\n'.join(f'[{Utils.get_title_url(item)}]({item})' for item in queue_slice)
            embed = discord.Embed(title=f'キュー[{i+1}/{PAGES}]', description=queue_description, color=0xffffff)
            await ctx.channel.send(embed=embed)

    # Save Playlists Date
    if playlists is not None:
        for playlist in playlists:
            Playlist.record_play_date(f'{playlist}.json',datetime.now())
        Playlist.save_playlists_date()

    endtime = time.time()
    logger.debug(f'Play Command processing time: {endtime - start}sec')

# Queue Command
@tree.command(
    guild = GUILD,
    name = 'queue',
    description = 'キューの確認'
)
async def queue(ctx:discord.Interaction):
    if Queue.get_queue():
        logger.debug('Queue Command')
        logger.debug(f'Queue Sum: {len(Queue.get_queue())}')
        logger.debug(f'Queue: {Queue.get_queue()}')
        embed = discord.Embed(title = 'キュー', description = f'全{len(Queue.get_queue())}曲', color = 0xffffff)
        await ctx.response.send_message(embed=embed)

        # Show Queue
        PAGES = len(Utils.chunk_list(Queue.get_queue(), 10))
        for i in range(PAGES):
            queue_slice = Queue.get_queue()[i*10:(i+1)*10]
            queue_description = '\n'.join(f'[{Utils.get_title_url(item)}]({item})' for item in queue_slice)
            embed = discord.Embed(title=f'キュー[{i+1}/{PAGES}]', description=queue_description, color=0xffffff)
            await ctx.channel.send(embed=embed)
    else:
        embed=discord.Embed(title=':warning:キューに曲が入っていません。', color=0xffff00)
        await ctx.response.send_message(embed=embed)
        logger.warning('Queue is empty')

# Skip Command
@tree.command(
    guild = GUILD,
    name = 'skip',
    description = '現在の曲をスキップします。'
)
async def skip(ctx:discord.Interaction, index:int = None):
    global IS_LOOP,NVIDEO
    logger.debug('Skip Command')
    # Check if User is connected to Voice Channel
    if ctx.user.voice is None:
        embed = discord.Embed(title = ':warning:ボイスチャンネルに接続してください。', color = 0xff0000)
        await ctx.response.send_message(embed=embed)
        logger.warning('User is not connected to Voice Channel')
        return
    if index is not None:
        if index < 1:
            embed = discord.Embed(title = ':warning:1曲未満をスキップすることはできません。',color=0xff0000)
            await ctx.response.send_message(embed=embed)
            logger.warning('Index is less than 1')
            return
        index = index - 1
    else:
        index = 0

    vc = discord.utils.get(client.voice_clients, guild=ctx.guild)

    try:
        NVIDEO.close()
    except:
        pass

    if (vc and vc.is_playing()):
        if IS_LOOP:
            IS_LOOP = False
            embed = discord.Embed(title = 'ループ再生を解除しました。', color = 0xffffff)
            logger.debug('Loop is False')
            await ctx.channel.send(embed=embed)
        Queue.skip_queue(index)
        if len(Queue.get_queue()) == 0:
            embed = discord.Embed(title = ':warning:キューに曲がありません。', color = 0xffff00)
            logger.warning('Queue is empty')
            await ctx.response.send_message(embed=embed)
            vc.stop()
            return
        embed = discord.Embed(title = f'{index+1}曲をスキップしました。', description = f'{Utils.get_title_url(Queue.get_queue()[0])}を再生します。', color = 0xffffff)
        logger.debug(f'Skip Music: {index+1}')
        logger.debug(f'Next Music: {Utils.get_title_url(Queue.get_queue()[0])}')
        await ctx.response.send_message(embed=embed)
        vc.stop()
    else:
        embed = discord.Embed(title = ':warning:再生中の曲がありません。', color = 0xffff00)
        logger.warning('Music is Not playing')
        await ctx.response.send_message(embed=embed)

# loop Command
@tree.command(
    guild = GUILD,
    name = 'loop',
    description = 'ループの設定'
)
async def loop(ctx:discord.Interaction):
    global IS_LOOP
    vc = discord.utils.get(client.voice_clients, guild=ctx.guild)
    if vc and vc.is_playing():
        if IS_LOOP:
            IS_LOOP = False
            embed = discord.Embed(title = 'ループ再生を解除しました。', color = 0xffffff)
            logger.debug('Loop is False')
            await ctx.response.send_message(embed=embed)
        else:
            IS_LOOP = True
            embed = discord.Embed(title = 'ループ再生を設定しました。', color = 0xffffff)
            logger.debug('Loop is True')
            await ctx.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title = ':warning:再生中の曲がありません。', color = 0xffff00)
        logger.warning('Music is Not playing')
        await ctx.response.send_message(embed=embed)

# Playlist Commands
# Create Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストを作成',
    description = 'プレイリストを作成します。'
)
@discord.app_commands.describe(
    urls = '動画のURL',
    playlist = 'プレイリスト名',
    locked = 'プレイリストの編集を禁止する'
)
async def create_playlist(ctx:discord.Interaction, playlist:str, urls:str, locked:bool):
    if Playlist.check_file(playlist):
        embed = discord.Embed(title='プレイリスト作成', description='プレイリストが既に存在します。', color=0xff0000)
        await ctx.response.send_message(embed=embed)
        logger.warning('Playlist already exists')
        return
    else:
        await ctx.response.defer()

        urls = urls.split(',')
        urls = Utils.delete_space(urls)
        # Delete Duplicate URLs
        if len(urls) != len(list(dict.fromkeys(urls))):
            embed = discord.Embed(title = ':warning:重複したURLは削除されました。', color = 0xffffff)
            logger.debug('Delete Duplicate URLs')
            await ctx.channel.send(embed = embed)
        urls = list(dict.fromkeys(urls))
        urls, error = Utils.check_url(urls)

        # Check if Error Occurred
        if error:
            embed = discord.Embed(title = ':warning:以下のエラーが発生しました。', description = '\n'.join(error), color = 0xff0000)
            await ctx.channel.send(embed = embed)
            logger.error(f'CheckURLErrors: {error}')

        # Check if URL does not exist
        if len(urls) == 0:
            embed = discord.Embed(title = ':warning:無効なURLが指定されました、URLを確認して再度実行してください。', color = 0xff0000)
            await ctx.followup.send(embed = embed)
            logger.warning('URL does not exist')
            return

        json_list = {'owner':[ctx.user.id],'locked':locked,'urls':urls}
        try:
            with open(f'{PLAYLIST_PATH}{playlist}.json','w',encoding='utf-8') as f:
                json.dump(json_list,f,indent=2,ensure_ascii=False)
        except Exception as e:
            embed=discord.Embed(title = ':warning:使用できない文字が入っています、別の名前に変えてください。', color=0xffffff)
            await ctx.followup.send(embed=embed)
            logger.warning(f'NameError_JSON: {e}')
            return

        embed=discord.Embed(title=f'プレイリスト:{playlist}を作成しました。',description='以下のURLをを追加しました。',color=0xffffff)
        Playlist.record_play_date(f'{playlist}.json',datetime.now())
        Playlist.save_playlists_date()
        await ctx.followup.send(embed=embed)
        logger.info(f'Create Playlist: {playlist}')

        # Show Queue
        PAGES = len(Utils.chunk_list(urls, 10))
        for i in range(PAGES):
            queue_slice = urls[i*10:(i+1)*10]
            queue_description = '\n'.join(f'[{Utils.get_title_url(item)}]({item})' for item in queue_slice)
            embed = discord.Embed(title = f'プレイリスト:{playlist}の曲の一覧{i+1}/{PAGES}', description=queue_description, color=0xffffff)
            embed.set_footer(text = f'プレイリストに登録された曲数:{len(urls)}曲')
            await ctx.channel.send(embed=embed)

# Add music to Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストに曲を追加',
    description = 'プレイリストに曲を追加します。'
)
@discord.app_commands.describe(
    urls = '動画のURL',
    playlist = 'プレイリスト名'
)
@app_commands.autocomplete(playlist = playlist_autocomplete)
async def add_music_to_playlist(ctx:discord.Interaction, playlist:str, urls:str):
    if not os.path.exists(f'{PLAYLIST_PATH}{playlist}.json'):
        embed = discord.Embed(title = f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。', color = 0xffff00)
        await ctx.response.send_message(embed=embed)
        logger.warning('Playlist does not exist')
        return
    # Set Start Time for Debugging
    start = time.time()

    await ctx.response.defer()
    urls = urls.split(',')
    urls = Utils.delete_space(urls)
    # Delete Duplicate URLs
    if len(urls) != len(list(dict.fromkeys(urls))):
        embed = discord.Embed(title = ':warning:重複したURLは削除されました。', color = 0xffffff)
        logger.debug('Delete Duplicate URLs')
        await ctx.channel.send(embed = embed)
    urls = list(dict.fromkeys(urls))
    urls, error = Utils.check_url(urls)

    # Check if Error Occurred
    if error:
        embed = discord.Embed(title = ':warning:以下のエラーが発生しました。', description = '\n'.join(error), color = 0xff0000)
        await ctx.channel.send(embed = embed)
        logger.error(f'CheckURLErrors: {error}')

    # Check if URL does not exist
    if len(urls) == 0:
        embed = discord.Embed(title = ':warning:無効なURLが指定されました、URLを確認して再度実行してください。', color = 0xff0000)
        await ctx.followup.send(embed = embed)
        logger.warning('URL does not exist')
        return

    with open(f'{PLAYLIST_PATH}{playlist}.json','r',encoding='utf-8') as f:
        json_list = json.load(f)
        if json_list['locked']:
            if ctx.user.id not in json_list['owner']:
                embed = discord.Embed(title = f':warning:プレイリスト{playlist}は編集が禁止されています。', color = 0xffff00)
                await ctx.followup.send(embed=embed)
                logger.warning('Playlist is locked')
                return

        skip_urls = []

    # Delete Duplicate URLs
    for url in urls[:]:
        if url in json_list['urls']:
            skip_urls.append(url)
            urls.remove(url)

    if len(skip_urls) != 0:
        embed = discord.Embed(title = ':warning:登録済みのURLはスキップされました。', color = 0xffff00)
        await ctx.channel.send(embed = embed)

    if len(urls) == 0:
        embed=discord.Embed(title=':warning:プレイリストに登録できるURLがありません、URLを確認し再度コマンドを実行してください。',color=0xffffff)
        await ctx.followup.send(embed = embed)
        logger.warning('URL does not exist')
        return

    json_list['urls'].extend(urls)
    with open(f'{PLAYLIST_PATH}{playlist}.json','w',encoding='utf-8') as f:
        json.dump(json_list,f,indent=2,ensure_ascii=False)
    embed=discord.Embed(title=f'プレイリスト:{playlist}に曲を追加しました。',description='以下のURLをを追加しました。',color=0xffffff)
    Playlist.record_play_date(f'{playlist}.json',datetime.now())
    Playlist.save_playlists_date()

    endtime = time.time()
    logger.debug(f'Add Music to Playlist Command processing time: {endtime - start}sec')
    logger.info(f'Add Music to Playlist: {playlist}')
    await ctx.followup.send(embed=embed)

    # Show Queue
    PAGES = len(Utils.chunk_list(urls, 10))
    for i in range(PAGES):
        queue_slice = urls[i*10:(i+1)*10]
        queue_description = '\n'.join(f'[{Utils.get_title_url(item)}]({item})' for item in queue_slice)
        embed = discord.Embed(title = f'プレイリスト:{playlist}の曲の一覧{i+1}/{PAGES}', description=queue_description, color=0xffffff)
        embed.set_footer(text=f'プレイリストに追加された曲数:{len(urls)}曲')
        await ctx.channel.send(embed = embed)

# Delete Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストを削除',
    description = 'プレイリストを削除します。'
)
@discord.app_commands.describe(
    playlist = 'プレイリスト名'
)
@app_commands.autocomplete(playlist = playlist_autocomplete)
async def delete_playlist(ctx:discord.Interaction, playlist:str):
    if not os.path.exists(f'{PLAYLIST_PATH}{playlist}.json'):
        embed = discord.Embed(title = f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。', color = 0xffff00)
        await ctx.response.send_message(embed = embed)
        return

    with open(f'{PLAYLIST_PATH}{playlist}.json','r',encoding='utf-8') as f:
        json_list = json.load(f)
        if json_list['locked']:
            if ctx.user.id not in json_list['owner']:
                embed = discord.Embed(title = f':warning:プレイリスト{playlist}は編集が禁止されています。', color = 0xffff00)
                await ctx.response.send_message(embed = embed)
                return
    await ctx.response.send_modal(DeleteInput(playlist))

# Delete music from Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストから曲を削除',
    description = 'プレイリストに登録された曲を削除します。'
)
@discord.app_commands.describe(
    urls = '動画のURL',
    playlist = 'プレイリスト名'
)
@app_commands.autocomplete(playlist = playlist_autocomplete)
async def delete_music_from_playlist(ctx:discord.Interaction, playlist:str, urls:str):
    if not os.path.exists(f'{PLAYLIST_PATH}{playlist}.json'):
        embed = discord.Embed(title = f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。', color = 0xffff00)
        await ctx.response.send_message(embed = embed)
        return
    else:
        urls = urls.split(',')
        urls = Utils.delete_space(urls)
        with open(f'{PLAYLIST_PATH}{playlist}.json','r',encoding='utf-8') as f:
            json_list = json.load(f)
            if json_list['locked']:
                if ctx.user.id not in json_list['owner']:
                    embed = discord.Embed(title = f':warning:プレイリスト{playlist}は編集が禁止されています。', color = 0xffff00)
                    await ctx.response.send_message(embed = embed)
                    logger.warning('Playlist is locked')
                    return

        targets_urls = list(set(urls) & set(json_list['urls']))

        if not targets_urls:
            embed = discord.Embed(title = ':warning:指定されたURLはプレイリストに登録されていません。', color = 0xffff00)
            await ctx.response.send_message(embed = embed)
            logger.warning('URL does not exist')
            return

        for target in targets_urls:
            json_list['urls'].remove(target)

        if len(json_list['urls']) == 0:
            os.remove(f'{PLAYLIST_PATH}{playlist}.json')
            embed = discord.Embed(title = f':warning:プレイリストに登録されている曲がなくなったため、プレイリスト：{playlist}を削除しました。', color = 0xffff00)
            await ctx.response.send_message(embed = embed)
            logger.warning('Playlist is empty and deleted.')
            return

        with open(f'{PLAYLIST_PATH}{playlist}.json','w',encoding='utf-8') as f:
            json.dump(json_list,f,indent=2,ensure_ascii=False)
        embed = discord.Embed(title = f'プレイリスト:{playlist}から曲を削除しました。', description='削除後のプレイリストの曲一覧はこちらです。', color = 0xffffff)
        await ctx.response.send_message(embed = embed)
        logger.info(f'Delete Music from Playlist: {playlist}')
        Playlist.record_play_date(f'{playlist}.json',datetime.now())
        Playlist.save_playlists_date()

        # Show Queue
        PAGES = len(Utils.chunk_list(json_list['urls'], 10))
        for i in range(PAGES):
            queue_slice = json_list['urls'][i*10:(i+1)*10]
            queue_description = '\n'.join(f'[{Utils.get_title_url(item)}]({item})' for item in queue_slice)
            embed = discord.Embed(title = f'プレイリスト:{playlist}の曲の一覧{i+1}/{PAGES}', description=queue_description, color=0xffffff)
            embed.set_footer(text=f'プレイリストに登録された曲数:{len(json_list["urls"])}曲')
            await ctx.channel.send(embed = embed)



# Rename Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリスト名を変更',
    description = 'プレイリスト名を変更します。'
)
@discord.app_commands.describe(
    playlist = 'プレイリスト名',
    new_playlist = '新しいプレイリスト名'
)
@app_commands.autocomplete(playlist = playlist_autocomplete)
async def rename_playlist(ctx:discord.Interaction, playlist:str, new_playlist:str):
    if not os.path.exists(f'{PLAYLIST_PATH}{playlist}.json'):
        embed = discord.Embed(title = f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。', color = 0xffff00)
        await ctx.response.send_message(embed = embed)
        logger.warning('Playlist does not exist')
        return
    elif os.path.exists(f'{PLAYLIST_PATH}{new_playlist}.json'):
        embed = discord.Embed(title = f':warning:プレイリスト{new_playlist}が既に存在します。', color = 0xffff00)
        await ctx.response.send_message(embed = embed)
        logger.warning('Playlist already exists')
        return
    else:
        Playlist.rename_playlist(playlist,new_playlist)
        embed = discord.Embed(title = f'プレイリスト名を{new_playlist}に変更しました。', color = 0xffffff)
        await ctx.response.send_message(embed = embed)

# Show Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリスト一覧を表示',
    description = '登録されているプレイリスト一覧を表示します。'
)
async def show_playlist(ctx:discord.Interaction):
    lists = os.listdir(PLAYLIST_PATH)
    logger.debug(f'Playlist Files: {lists}')
    if lists == []:
        embed = discord.Embed(title = ':warning:登録されているプレイリストが存在しません。', color = 0xffff00)
        await ctx.response.send_message(embed = embed)
        logger.warning('Playlist does not exist')
        return
    embed = discord.Embed(title = '登録されているプレイリスト一覧を表示します。', color = 0xffffff)
    await ctx.response.send_message(embed = embed)
    # Show Playlist
    PAGES = len(Utils.chunk_list(lists, 10))
    for i in range(PAGES):
        queue_slice = lists[i*10:(i+1)*10]
        queue_description = '\n'.join(f'・{item}' for item in queue_slice)
        embed = discord.Embed(title = f'登録されているプレイリスト一覧{i+1}/{PAGES}', description=queue_description, color=0xffffff)
        embed.set_footer(text=f'登録されているプレイリスト数:{len(lists)}')
        await ctx.channel.send(embed = embed)
    logger.info('Show Playlist Command')

# Show Music from Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストに登録されている曲を表示',
    description = 'プレイリストに登録された曲を表示します。'
)
@discord.app_commands.describe(
    playlist = 'プレイリスト名'
)
@app_commands.autocomplete(playlist = playlist_autocomplete)
async def show_music_from_playlist(ctx:discord.Interaction, playlist:str):
    if not os.path.exists(f'{PLAYLIST_PATH}{playlist}.json'):
        embed = discord.Embed(title = f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。', color = 0xffff00)
        await ctx.response.send_message(embed = embed)
        return
    with open(f'{PLAYLIST_PATH}{playlist}.json','r',encoding='utf-8') as f:
        json_list = json.load(f)
        embed = discord.Embed(title = f'プレイリスト:{playlist}に登録されている曲一覧', color = 0xffffff)
        await ctx.response.send_message(embed = embed)
        # Show Queue
        PAGES = len(Utils.chunk_list(json_list['urls'], 10))
        for i in range(PAGES):
            queue_slice = json_list['urls'][i*10:(i+1)*10]
            queue_description = '\n'.join(f'[{Utils.get_title_url(item)}]({item})' for item in queue_slice)
            embed = discord.Embed(title = f'プレイリスト:{playlist}の曲の一覧{i+1}/{PAGES}', description=queue_description, color=0xffffff)
            embed.set_footer(text=f'プレイリストに登録された曲数:{len(json_list["urls"])}曲')
            await ctx.channel.send(embed = embed)

# Change Playlist Lock Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストのロックを変更',
    description = 'プレイリストの編集ロックを変更します。'
)
@discord.app_commands.describe(
    playlist = 'プレイリスト名',
    locked = 'プレイリストの編集を禁止する'
)
@app_commands.autocomplete(playlist = playlist_autocomplete)
async def change_playlist_lock(ctx:discord.Interaction, playlist:str, locked:bool):
    if not os.path.exists(f'{PLAYLIST_PATH}{playlist}.json'):
        embed = discord.Embed(title = f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。', color = 0xffff00)
        await ctx.response.send_message(embed = embed)
        return
    await ctx.response.defer()
    with open(f'{PLAYLIST_PATH}{playlist}.json','r',encoding='utf-8') as f:
        json_list = json.load(f)
    if ctx.user.id not in json_list['owner']:
        embed = discord.Embed(title = f':warning:プレイリストの編集ロックを変更できるのは作成者のみです。', color = 0xff0000)
        await ctx.followup.send(embed = embed)
        logger.warning('Playlist is locked')
        return
    json_list['locked'] = locked
    with open(f'{PLAYLIST_PATH}{playlist}.json','w',encoding='utf-8') as f:
        json.dump(json_list,f,indent=2,ensure_ascii=False)
        result =  'ロックを有効化しました。' if locked else 'ロックを無効化しました。'
        embed = discord.Embed(title = f'プレイリスト:{playlist}の編集{result}', color = 0xffffff)
    await ctx.followup.send(embed = embed)

# Join Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストを結合する',
    description = '指定した2つのプレイリストを結合します。'
)
@discord.app_commands.describe(
    parent_playlist = '結合先の親プレイリスト名',
    child_playlist = '結合する子プレイリスト名'
)
@app_commands.autocomplete(parent_playlist = playlist_autocomplete, child_playlist = playlist_autocomplete)
async def join_playlist(ctx:discord.Interaction, parent_playlist:str, child_playlist:str):
    if parent_playlist == child_playlist:
        embed = discord.Embed(title = ':warning:同じプレイリスト同士は結合できません。', color = 0xffff00)
        logger.warning('equal playlist')
        await ctx.response.send_message(embed = embed)
        return
    if not (os.path.exists(f'{PLAYLIST_PATH}{parent_playlist}.json') and os.path.exists(f'{PLAYLIST_PATH}{child_playlist}.json')):
        embed = discord.Embed(title = f':warning:プレイリスト{parent_playlist}または{child_playlist}が存在しません、名前が合っているか確認してください。', color = 0xff0000)
        await ctx.response.send_message(embed = embed)
        return
    await ctx.response.defer()
    with open(f'{PLAYLIST_PATH}{parent_playlist}.json','r',encoding='utf-8') as f:
        parent_json = json.load(f)
    if parent_json['locked']:
        if ctx.user.id not in parent_json['owner']:
            embed = discord.Embed(title = f':warning:プレイリスト{parent_playlist}は編集が禁止されています。', color = 0xffff00)
            await ctx.followup.send(embed = embed)
            logger.warning('Playlist is locked')
            return
    with open(f'{PLAYLIST_PATH}{child_playlist}.json','r',encoding='utf-8') as f:
        child_json = json.load(f)

    skip_urls = []

    for url in child_json['urls'][:]:
        if url not in parent_json['urls']:
            parent_json['urls'].append(url)
            skip_urls.append(url)
        else:
            child_json['urls'].remove(url)

    if len(skip_urls) != 0:
        embed = discord.Embed(title = ':warning:登録済みのURLはスキップされました。', color = 0xffff00)
        await ctx.channel.send(embed = embed)

    if len(child_json['urls']) == 0:
        embed=discord.Embed(title=':warning:プレイリストに新たに登録できるURLがありませんでした。',color=0xffffff)
        await ctx.followup.send(embed = embed)
        logger.warning('URL does not exist')
        return

    json_list = {'owner':parent_json['owner'],'locked':parent_json['locked'],'urls':parent_json['urls']}
    with open(f'{PLAYLIST_PATH}{parent_playlist}.json','w',encoding='utf-8') as f:
        json.dump(json_list,f,indent=2,ensure_ascii=False)
    embed = discord.Embed(title = f'プレイリスト:{child_playlist}を{parent_playlist}に結合しました。', color = 0xffffff)
    await ctx.followup.send(embed = embed)

    # Show Queue
    PAGES = len(Utils.chunk_list(child_json['urls'], 10))
    for i in range(PAGES):
        queue_slice = child_json['urls'][i*10:(i+1)*10]
        queue_description = '\n'.join(f'[{Utils.get_title_url(item)}]({item})' for item in queue_slice)
        embed = discord.Embed(title = f'プレイリスト:{parent_playlist}に追加された曲の一覧{i+1}/{PAGES}', description=queue_description, color=0xffffff)
        embed.set_footer(text=f'プレイリストに登録された曲数:{len(child_json["urls"])}曲')
        await ctx.channel.send(embed = embed)

# Reset Bot Command
@tree.command(
    guild = GUILD,
    name = 'reset',
    description = 'Botを再起動します。'
)
async def reset_bot(ctx:discord.Interaction):
    global NEXT_SONG, IS_LOOP
    NEXT_SONG = None
    IS_LOOP = False
    vc = discord.utils.get(client.voice_clients,guild=ctx.guild)
    try:
        vc.cleanup()
        await vc.disconnect()
    except:
        pass
    Queue.clear_queue()
    await client.change_presence(activity = None)
    embed=discord.Embed(title='リセットします。', color=0xffffff)
    await ctx.response.send_message(embed=embed)
@reset_bot.error
async def play_error(ctx:discord.Interaction,error):
    await ctx.response.send_message(error)
    return

@tree.command(
    guild = GUILD,
    name = 'log',
    description = '件数を指定してログを表示します。'
)
async def log(ctx:discord.Interaction, num:int):
    with open('Log/PlayAudio.log', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        lines = lines[-num:]
        lines = ''.join(lines)

        # limit 2000 characters
        if len(lines) > 2000:
            lines = lines[-2000:]

        await ctx.response.send_message(lines)

# Disconnect Bot Command
@client.event
async def on_voice_state_update(member, before, after):
    global NEXT_SONG, IS_LOOP
    voice_state = member.guild.voice_client
    if voice_state is not None and len(voice_state.channel.members) == 1:
        voice_state.cleanup()
        IS_LOOP = False
        NEXT_SONG = None
        Queue.clear_queue()
        await client.change_presence(activity = None)
        await voice_state.disconnect()

# Discord Bot Start
@client.event
async def on_ready():
    logger.info('Discord Bot Started...')
    check_music.start()
    await tree.sync(guild=GUILD)
    logger.info('Discord Bot Command Synced...')

@tree.error
async def on_app_command_error(ctx: discord.Interaction, error):
    logger.critical(f'Error: {error}')
    await ctx.response.send_message(f'CriticalError!!!: {error}')

client.run(TOKEN)