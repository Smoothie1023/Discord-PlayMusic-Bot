import json
import logging
import os
import random
import time
from collections import deque
from datetime import datetime
from typing import Literal
import urllib.request
from urllib.parse import urlparse, parse_qs

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Modal, View, text_input
from bs4 import BeautifulSoup
from niconico import NicoNico
import requests
from yt_dlp import YoutubeDL

import Downloader
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
Playlist = Playlist.Playlist()
# Queue Initialize
Queue = Queue.Queue()
# Utils Initialize
Utils = Utils.Utils()

# Youtube Streamming Function
def play_music(vc) -> None:
    global IS_LOOP
    if (len(Queue.get_queue()) == 0) and (not IS_LOOP):
        return
    if IS_LOOP:
        url = Queue.now_playing
    else:
        url = Queue.pop_queue()
    logger.info(f'Play Music: {url}')
    try:
        NVIDEO.close()
        logger.info("Closed NVideo")
    except:
        pass
    if "nico" in url:
        try:
            print(url)
            NVIDEO = NCLIENT.video.get_video(url)
            NVIDEO.connect()
            url = NVIDEO.download_link
            print(url)
        except:
            pass

    s_y = Player.streamming_youtube(url)

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a loudnorm'}
    try:
        vc.play(source=discord.FFmpegPCMAudio(s_y["url"],**ffmpeg_options),after=lambda e:play_music(vc))
    except Exception as e:
        logger.error(f'play_music_Error: {e}')
        return
    return s_y

# Notificate change Music
@tasks.loop(seconds=1)
async def check_music():
    global NEXT_SONG, IS_LOOP
    # Wait run Bot
    await client.wait_until_ready()
    vc_channel = client.get_channel(VC_CHANNEL_ID)
    channel = client.get_channel(CHANNEL_ID)

    try:
        if vc_channel.guild.voice_client:
            vc = discord.utils.get(client.voice_clients)
            if vc.is_playing():
                if IS_LOOP:
                    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="🔄"+Utils.get_title_url(Queue.now_playing)))
                else:
                    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="⏩"+Utils.get_title_url(Queue.now_playing)))

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


def create_next_embed(url):
    embed=discord.Embed(title="次の曲",description=f"[{Utils.get_title_url(url)}]({url})", color=0xffffff)
    if "youtu" in url:
        embed.set_image(url=f"https://img.youtube.com/vi/{Utils.get_video_id(url)}/mqdefault.jpg")
        logger.info("Get Youtube thumbnail")
    elif "nico" in url:
        with requests.Session() as session:
            url=f"https://ext.nicovideo.jp/api/getthumbinfo/{Utils.get_video_id(url)}"
            url=session.get(url)
            url=url.text[url.text.find("<thumbnail_url>")+15:url.text.find("</thumbnail_url>")]+".L"
            if session.get(url).status_code!=200:
                url=url[:-2]
            embed.set_image(url=url)
            logger.info("Get niconico thumbnail")
            logger.info(url)
    else:
        logger.info("Can't Get thumbnail")
    return embed

# Discord Bot Commands
# Play Command
@tree.command(
    guild = GUILD,
    name = 'play',
    description = '指定されたURL、プレイリストから曲を再生します。'
)
@discord.app_commands.describe(
    urls = '動画のURL',
    playlist = 'プレイリスト名',
    shuffle = 'シャッフル再生'
)
async def play(ctx:discord.Interaction, urls:str = None, playlist:str = None,
                shuffle:Literal['シャッフル再生'] = None):
    logger.debug('Play Command')
    logger.debug(f'User: {ctx.user}')
    logger.debug('args')
    logger.debug(f'URL: {urls}')
    logger.debug(f'Playlist: {playlist}')
    logger.debug(f'Shuffle: {shuffle}')
    # Set Start Time for Debugging
    start = time.time()

    # Check if User is connected to Voice Channel
    if ctx.user.voice is None:
        embed = discord.Embed(title = ':warning:ボイスチャンネルに接続してください。', color = 0xffffff)
        await ctx.response.send_message(embed=embed)
        logger.warning('User is not connected to Voice Channel')
        return

    # Check if URL or Playlist Name is correct
    if (urls is None and playlist is None) or (urls is not None and playlist is not None):
        embed = discord.Embed(title = ':warning:URLかプレイリスト名の片方を指定してください。', color = 0xffffff)
        await ctx.response.send_message(embed=embed)
        logger.warning('URL or playlist name is incorrect')
        return

    await ctx.response.defer()

    # Select URL Option
    if urls is not None:
        logger.debug('URL is not None')
        urls = urls.split(',')
        urls = Utils.delete_space(urls)
        # Delete Duplicate URLs
        if len(urls) != len(list(set(urls))):
            embed = discord.Embed(title = ':warning:重複したURLは削除されました。', color = 0xffffff)
            await ctx.channel.send(embed = embed)
        urls = list(dict.fromkeys(urls))
        urls, error = Utils.check_url(urls)
        logger.info(f'URLs: {urls}')

        # Check if Error Occurred
        if error:
            embed = discord.Embed(title = ':warning:以下のエラーが発生しました。', description = '\n'.join(error), color = 0xff0000)
            await ctx.channel.send(embed = embed)
            logger.warning(f'CheckURLErrors: {error}')

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

    vc = discord.utils.get(client.voice_clients,guild=ctx.guild)

    if not vc.is_playing():
        embed = discord.Embed(description = f'[{Utils.get_title_url(Queue.get_queue()[0])}]({Queue.get_queue()[0]})を再生します。', color = 0xffffff)
        if len(Queue.get_queue()) != 1:
            embed.set_footer(text=f"他{len(urls)-1}曲はキューに追加しました。")
        await ctx.followup.send(embed = embed)
        play_music(vc)
    else:
        embed = discord.Embed(description = f'{len(urls)}曲をキューに追加しました。', color = 0xffffff)
        await ctx.followup.send(embed = embed)
        PAGES = len(Utils.chunk_list(urls, 10))
        for i in range(PAGES):
            queue_slice = urls[i*10:(i+1)*10]
            queue_description = '\n'.join(f'[{Utils.get_title_url(item)}]({item})' for item in queue_slice)
            embed = discord.Embed(title=f'キュー[{i+1}/{PAGES}]', description=queue_description, color=0xffffff)
            await ctx.channel.send(embed=embed)


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
        embed = discord.Embed(title = ':warning:ボイスチャンネルに接続してください。', color = 0xffffff)
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
            await ctx.channel.send(embed=embed)
        Queue.skip_queue(index)
        if len(Queue.get_queue()) == 0:
            embed = discord.Embed(title = ':warning:キューに曲がありません。', color = 0xffff00)
            await ctx.response.send_message(embed=embed)
            vc.stop()
            return
        embed = discord.Embed(title = f'{index+1}曲をスキップしました。', description = f'{Utils.get_title_url(Queue.get_queue()[0])}を再生します。', color = 0xffffff)
        await ctx.response.send_message(embed=embed)
        vc.stop()
    else:
        embed = discord.Embed(title = ':warning:再生中の曲がありません。', color = 0xffff00)
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
            await ctx.response.send_message(embed=embed)
        else:
            IS_LOOP = True
            embed = discord.Embed(title = 'ループ再生を設定しました。', color = 0xffffff)
            await ctx.response.send_message(embed=embed)
        logger.debug('IS_LOOP: {IS_LOOP}')
    else:
        embed = discord.Embed(title = ':warning:再生中の曲がありません。', color = 0xffff00)
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
    locked = '作成者以外プレイリストの編集を禁止する'
)
async def create_playlist(ctx:discord.Interaction, playlist:str, urls:str, locked:bool):
    if Playlist.check_file():
        embed = discord.Embed(title='プレイリスト作成', description='プレイリストが既に存在します。', color=0xff0000)
        await ctx.response.send_message(embed=embed)
        return
    else:
        urls = urls.split(',')
        urls = Utils.delete_space(urls)
        await ctx.response.send_message('Create Playlist Command')

# Add music to Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストに曲を追加',
    description = 'プレイリストに曲を追加します。'
)
async def add_music_to_playlist(ctx:discord.Interaction):
    await ctx.response.send_message('Add Music to Playlist Command')

# Delete Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストを削除',
    description = 'プレイリストを削除します。'
)
async def delete_playlist(ctx:discord.Interaction):
    await ctx.response.send_message('Delete Playlist Command')

# Delete music from Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストから曲を削除',
    description = 'プレイリストに登録された曲を削除します。'
)
async def delete_music_from_playlist(ctx:discord.Interaction):
    await ctx.response.send_message('Delete Music from Playlist Command')

# Rename Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリスト名を変更',
    description = 'プレイリスト名を変更します。'
)
async def rename_playlist(ctx:discord.Interaction):
    await ctx.response.send_message('Rename Playlist Command')

# Show Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリスト一覧を表示',
    description = '登録されているプレイリスト一覧を表示します。'
)
async def show_playlist(ctx:discord.Interaction):
    await ctx.response.send_message('Show Playlist Command')

# Show Music from Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストに登録されている曲を表示',
    description = 'プレイリストに登録された曲を表示します。'
)
async def show_music_from_playlist(ctx:discord.Interaction):
    await ctx.response.send_message('Show Music from Playlist Command')

# Change Playlist Lock Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストのロックを変更',
    description = 'プレイリストの編集ロックを変更します。'
)
async def change_playlist_lock(ctx:discord.Interaction):
    await ctx.response.send_message('Change Playlist Lock Command')

# Join Playlist Command
@tree.command(
    guild = GUILD,
    name = 'プレイリストを結合する',
    description = '指定した2つのプレイリストを結合します。'
)
async def join_playlist(ctx:discord.Interaction):
    await ctx.response.send_message('Join Playlist Command')

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
    vc.cleanup()
    Queue.clear_queue()
    await client.change_presence(activity = None)
    await vc.disconnect()
    embed=discord.Embed(title="リセットします。",color=0xffffff)
    await ctx.response.send_message(embed=embed)

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

#@tree.error
#async def on_app_command_error(ctx: discord.Interaction, error):
    #logger.error(f'Error: {error}')
    #await ctx.response.send_message(f'Error: {error}')

client.run(TOKEN)