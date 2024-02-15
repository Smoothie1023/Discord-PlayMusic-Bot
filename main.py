import os
import random
import json
import time
import logging
import re
import requests
from datetime import datetime
from collections import deque
import urllib.request
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, View, text_input
from yt_dlp import YoutubeDL
from niconico import NicoNico

import Downloader
import Playlist
import Utils

# Setup Logging
logger = logging.getLogger('PlayAudio')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('Log/PlayAudio.log')
logger.addHandler(handler)
fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(fmt)

logger.info('Starting PlayAudio')

# Constants
# Discord Bot Initialize
client = discord.Client(intents = discord.Intents.default())
tree = discord.app_commands.CommandTree(client)
# Discord Token Folder Path
DISCORD_TOKEN_FOLDER_PATH = 'DiscordTokens/'
# Supported Websites
SUPPORTED_WEBSITES = re.compile(r"youtube|youtu.be|nicovideo|nico|twitter|t.co|soundcloud.com|x|cdn.discordapp.com")
# Load Discord Tokens
with open(os.path.join(DISCORD_TOKEN_FOLDER_PATH,'token.txt')) as t, \
    open(os.path.join(DISCORD_TOKEN_FOLDER_PATH,'guild_id.txt')) as g, \
    open(os.path.join(DISCORD_TOKEN_FOLDER_PATH,'vc_channel_id.txt')) as v, \
    open(os.path.join(DISCORD_TOKEN_FOLDER_PATH,'channel_id.txt')) as c:
        TOKEN = t.read()
        GUILD_ID = g.read()
        VC_CHANNEL_ID = int(v.read())
        CHANNEL_ID = int(c.read())
        GUILD = discord.Object(GUILD_ID)

logger.info('Discord Token Loaded')
logger.debug(f'Token: {TOKEN}')
logger.debug(f'Guild ID: {GUILD_ID}')
logger.debug(f'VC Channel ID: {VC_CHANNEL_ID}')
logger.debug(f'Channel ID: {CHANNEL_ID}')

# Downloader Initialize
Downloader = Downloader.Downloader()
# Playlist Initialize
Playlist = Playlist.Playlist()
# Utils Initialize
Utils = Utils.Utils()

# Discord Bot Commands
# Play Command
@tree.command(
    guild = GUILD,
    name = 'play',
    description = '指定されたURL、プレイリストから曲を再生します。'
)
async def play(ctx:discord.Interaction):
    await ctx.response.send_message('Play Command')

# Queue Command
@tree.command(
    guild = GUILD,
    name = 'queue',
    description = 'キューの確認'
)
async def queue(ctx:discord.Interaction):
    await ctx.response.send_message('Queue Command')

# Skip Command
@tree.command(
    guild = GUILD,
    name = 'skip',
    description = '現在の曲をスキップします。'
)
async def skip(ctx:discord.Interaction):
    await ctx.response.send_message('Skip Command')

# loop Command
@tree.command(
    guild = GUILD,
    name = 'loop',
    description = 'ループの設定'
)
async def loop(ctx:discord.Interaction):
    await ctx.response.send_message('Loop Command')

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
    await ctx.response.send_message('Reset Bot Command')

# Discord Bot Start
@client.event
async def on_ready():
    logger.info('Discord Bot Started...')
    await tree.sync(guild=GUILD)
    logger.info('Discord Bot Command Synced...')

@tree.error
async def on_app_command_error(ctx: discord.Interaction, error):
    logger.error(f'Error: {error}')

client.run(TOKEN)