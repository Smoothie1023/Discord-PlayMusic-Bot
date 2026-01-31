# -*- coding: utf-8 -*-
"""プレイリスト管理関連のCog"""

import logging
import os
import time
from datetime import datetime
from typing import List

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, text_input
import orjson

logger = logging.getLogger('PlayAudio')


class DeleteInput(Modal, title='プレイリストを削除'):
    """プレイリスト削除確認モーダル"""
    text = text_input.TextInput(
        label='削除するプレイリスト名',
        placeholder='プレイリスト名',
        max_length=100,
        required=True
    )

    def __init__(self, playlist: str, playlist_path: str, playlist_manager):
        super().__init__(title='⚠削除後復元はできません！')
        self.playlist = playlist
        self.playlist_path = playlist_path
        self.playlist_manager = playlist_manager

    async def on_submit(self, interaction: discord.Interaction):
        if self.text.value == self.playlist:
            os.remove(f'{self.playlist_path}{self.playlist}.json')
            embed = discord.Embed(
                title=f'プレイリスト:{self.playlist}を削除しました。',
                color=0xffffff
            )
            self.playlist_manager.delete_playlists_date(self.playlist)
            await interaction.response.send_message(embed=embed)
            logger.info(f'Delete Playlist: {self.playlist}')
        else:
            embed = discord.Embed(title=':warning:プレイリスト名が一致しません。', color=0xffff00)
            await interaction.response.send_message(embed=embed)
            logger.warning('Playlist Name does not match')

    async def on_cancel(self, interaction: discord.Interaction):
        embed = discord.Embed(title='プレイリスト削除をキャンセルしました。', color=0xffffff)
        await interaction.response.send_message(embed=embed)
        logger.info('Cancel Delete Playlist')

    async def on_timeout(self):
        embed = discord.Embed(title='プレイリスト削除をキャンセルしました。', color=0xffffff)
        await self.message.edit(embed=embed)
        logger.info('Timeout Delete Playlist')

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        return await interaction.response.send_message(str(error))


class PlaylistCog(commands.Cog):
    """プレイリスト管理機能を提供するCog"""

    def __init__(self, bot: commands.Bot, config, playlist, utils):
        self.bot = bot
        self.config = config
        self.playlist = playlist
        self.utils = utils

    async def playlist_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """プレイリストのオートコンプリート"""
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

    @app_commands.command(name='プレイリストを作成', description='プレイリストを作成します。')
    @app_commands.describe(
        urls='動画のURL',
        playlist='プレイリスト名',
        locked='プレイリストの編集を禁止する'
    )
    async def create_playlist(
        self,
        ctx: discord.Interaction,
        playlist: str,
        urls: str,
        locked: bool
    ):
        """プレイリストを作成"""
        playlist_path = self.config.PLAYLIST_PATH

        if self.playlist.check_file(playlist):
            embed = discord.Embed(
                title='プレイリスト作成',
                description='プレイリストが既に存在します。',
                color=0xff0000
            )
            await ctx.response.send_message(embed=embed)
            logger.warning('Playlist already exists')
            return

        await ctx.response.defer()

        urls = urls.split(',')
        urls = self.utils.delete_space(urls)

        # 重複URL削除
        if len(urls) != len(list(dict.fromkeys(urls))):
            embed = discord.Embed(title=':warning:重複したURLは削除されました。', color=0xffffff)
            logger.debug('Delete Duplicate URLs')
            await ctx.channel.send(embed=embed)

        urls = list(dict.fromkeys(urls))
        urls, error = self.utils.check_url(urls)

        if error:
            embed = discord.Embed(
                title=':warning:以下のエラーが発生しました。',
                description='\n'.join(error),
                color=0xff0000
            )
            await ctx.channel.send(embed=embed)
            logger.error(f'CheckURLErrors: {error}')

        if len(urls) == 0:
            embed = discord.Embed(
                title=':warning:無効なURLが指定されました、URLを確認して再度実行してください。',
                color=0xff0000
            )
            await ctx.followup.send(embed=embed)
            return

        json_list = {'owner': [ctx.user.id], 'locked': locked, 'urls': urls}
        try:
            with open(f'{playlist_path}{playlist}.json', 'w', encoding='utf-8') as f:
                f.write(orjson.dumps(json_list, option=orjson.OPT_INDENT_2).decode('utf-8'))

            os.chmod(f'{playlist_path}{playlist}.json', 0o666)

        except Exception as e:
            embed = discord.Embed(
                title=':warning:使用できない文字が入っています、別の名前に変えてください。',
                color=0xffffff
            )
            await ctx.followup.send(embed=embed)
            logger.warning(f'NameError_JSON: {e}')
            return

        embed = discord.Embed(
            title=f'プレイリスト:{playlist}を作成しました。',
            description='以下のURLをを追加しました。',
            color=0xffffff
        )
        self.playlist.record_play_date(f'{playlist}.json', datetime.now())
        self.playlist.save_playlists_date()
        await ctx.followup.send(embed=embed)
        logger.info(f'Create Playlist: {playlist}')

        embed = self.utils.create_queue_embed(
            urls,
            f'プレイリスト:{playlist}の曲の一覧',
            f'プレイリストに追加された曲数:{len(urls)}曲'
        )
        await ctx.channel.send(embed=embed)

    @app_commands.command(name='プレイリストに曲を追加', description='プレイリストに曲を追加します。')
    @app_commands.describe(urls='動画のURL', playlist='プレイリスト名')
    async def add_music_to_playlist(
        self,
        ctx: discord.Interaction,
        playlist: str,
        urls: str
    ):
        """プレイリストに曲を追加"""
        playlist_path = self.config.PLAYLIST_PATH

        if not os.path.exists(f'{playlist_path}{playlist}.json'):
            embed = discord.Embed(
                title=f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。',
                color=0xffff00
            )
            await ctx.response.send_message(embed=embed)
            return

        start = time.time()
        await ctx.response.defer()

        urls = urls.split(',')
        urls = self.utils.delete_space(urls)

        if len(urls) != len(list(dict.fromkeys(urls))):
            embed = discord.Embed(title=':warning:重複したURLは削除されました。', color=0xffffff)
            await ctx.channel.send(embed=embed)

        urls = list(dict.fromkeys(urls))
        urls, error = self.utils.check_url(urls)

        if error:
            embed = discord.Embed(
                title=':warning:以下のエラーが発生しました。',
                description='\n'.join(error),
                color=0xff0000
            )
            await ctx.channel.send(embed=embed)
            logger.error(f'CheckURLErrors: {error}')

        if len(urls) == 0:
            embed = discord.Embed(
                title=':warning:無効なURLが指定されました、URLを確認して再度実行してください。',
                color=0xff0000
            )
            await ctx.followup.send(embed=embed)
            return

        with open(f'{playlist_path}{playlist}.json', 'r', encoding='utf-8') as f:
            json_list = orjson.loads(f.read())
            if json_list['locked']:
                if ctx.user.id not in json_list['owner']:
                    embed = discord.Embed(
                        title=f':warning:プレイリスト{playlist}は編集が禁止されています。',
                        color=0xffff00
                    )
                    await ctx.followup.send(embed=embed)
                    return

            skip_urls = []

        # 登録済みURL確認
        for url in urls[:]:
            if url in json_list['urls']:
                skip_urls.append(url)
                urls.remove(url)

        if len(skip_urls) != 0:
            embed = discord.Embed(title=':warning:登録済みのURLはスキップされました。', color=0xffff00)
            await ctx.channel.send(embed=embed)

        if len(urls) == 0:
            embed = discord.Embed(
                title=':warning:プレイリストに登録できるURLがありません、URLを確認し再度コマンドを実行してください。',
                color=0xffffff
            )
            await ctx.followup.send(embed=embed)
            return

        json_list['urls'].extend(urls)
        with open(f'{playlist_path}{playlist}.json', 'w', encoding='utf-8') as f:
            f.write(orjson.dumps(json_list, option=orjson.OPT_INDENT_2).decode('utf-8'))

        embed = discord.Embed(
            title=f'プレイリスト:{playlist}に曲を追加しました。',
            description='以下のURLをを追加しました。',
            color=0xffffff
        )
        self.playlist.record_play_date(f'{playlist}.json', datetime.now())
        self.playlist.save_playlists_date()

        endtime = time.time()
        logger.debug(f'Add Music to Playlist Command processing time: {endtime - start}sec')
        logger.info(f'Add Music to Playlist: {playlist}')
        await ctx.followup.send(embed=embed)

        embed = self.utils.create_queue_embed(
            urls,
            title=f'プレイリスト:{playlist}の曲の一覧',
            footer=f'プレイリストに追加された曲数:{len(urls)}曲',
            addPages=True
        )
        await ctx.channel.send(embed=embed)

    @app_commands.command(name='プレイリストを削除', description='プレイリストを削除します。')
    @app_commands.describe(playlist='プレイリスト名')
    async def delete_playlist(self, ctx: discord.Interaction, playlist: str):
        """プレイリストを削除"""
        playlist_path = self.config.PLAYLIST_PATH

        if not os.path.exists(f'{playlist_path}{playlist}.json'):
            embed = discord.Embed(
                title=f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。',
                color=0xffff00
            )
            await ctx.response.send_message(embed=embed)
            return

        with open(f'{playlist_path}{playlist}.json', 'r', encoding='utf-8') as f:
            json_list = orjson.loads(f.read())
            if json_list['locked']:
                if ctx.user.id not in json_list['owner']:
                    embed = discord.Embed(
                        title=f':warning:プレイリスト{playlist}は編集が禁止されています。',
                        color=0xffff00
                    )
                    await ctx.response.send_message(embed=embed)
                    return

        await ctx.response.send_modal(DeleteInput(playlist, playlist_path, self.playlist))

    @app_commands.command(name='プレイリストから曲を削除', description='プレイリストに登録された曲を削除します。')
    @app_commands.describe(urls='動画のURL', playlist='プレイリスト名')
    async def delete_music_from_playlist(
        self,
        ctx: discord.Interaction,
        playlist: str,
        urls: str
    ):
        """プレイリストから曲を削除"""
        playlist_path = self.config.PLAYLIST_PATH

        if not os.path.exists(f'{playlist_path}{playlist}.json'):
            embed = discord.Embed(
                title=f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。',
                color=0xffff00
            )
            await ctx.response.send_message(embed=embed)
            return

        urls = urls.split(',')
        urls = self.utils.delete_space(urls)

        with open(f'{playlist_path}{playlist}.json', 'r', encoding='utf-8') as f:
            json_list = orjson.loads(f.read())
            if json_list['locked']:
                if ctx.user.id not in json_list['owner']:
                    embed = discord.Embed(
                        title=f':warning:プレイリスト{playlist}は編集が禁止されています。',
                        color=0xffff00
                    )
                    await ctx.response.send_message(embed=embed)
                    return

        targets_urls = list(set(urls) & set(json_list['urls']))

        if not targets_urls:
            embed = discord.Embed(
                title=':warning:指定されたURLはプレイリストに登録されていません。',
                color=0xffff00
            )
            await ctx.response.send_message(embed=embed)
            return

        for target in targets_urls:
            json_list['urls'].remove(target)

        if len(json_list['urls']) == 0:
            os.remove(f'{playlist_path}{playlist}.json')
            embed = discord.Embed(
                title=f':warning:プレイリストに登録されている曲がなくなったため、プレイリスト：{playlist}を削除しました。',
                color=0xffff00
            )
            await ctx.response.send_message(embed=embed)
            return

        with open(f'{playlist_path}{playlist}.json', 'w', encoding='utf-8') as f:
            f.write(orjson.dumps(json_list, option=orjson.OPT_INDENT_2).decode('utf-8'))

        embed = discord.Embed(
            title=f'プレイリスト:{playlist}から曲を削除しました。',
            description='削除後のプレイリストの曲一覧はこちらです。',
            color=0xffffff
        )
        await ctx.response.send_message(embed=embed)
        logger.info(f'Delete Music from Playlist: {playlist}')
        self.playlist.record_play_date(f'{playlist}.json', datetime.now())
        self.playlist.save_playlists_date()

        embed = self.utils.create_queue_embed(
            json_list["urls"],
            title=f'プレイリスト:{playlist}の曲の一覧',
            footer=f'プレイリストに登録された曲数:{len(json_list["urls"])}曲',
            addPages=True
        )
        await ctx.channel.send(embed=embed)

    @app_commands.command(name='プレイリスト名を変更', description='プレイリスト名を変更します。')
    @app_commands.describe(playlist='プレイリスト名', new_playlist='新しいプレイリスト名')
    async def rename_playlist(
        self,
        ctx: discord.Interaction,
        playlist: str,
        new_playlist: str
    ):
        """プレイリスト名を変更"""
        playlist_path = self.config.PLAYLIST_PATH

        if not os.path.exists(f'{playlist_path}{playlist}.json'):
            embed = discord.Embed(
                title=f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。',
                color=0xffff00
            )
            await ctx.response.send_message(embed=embed)
            return
        elif os.path.exists(f'{playlist_path}{new_playlist}.json'):
            embed = discord.Embed(
                title=f':warning:プレイリスト{new_playlist}が既に存在します。',
                color=0xffff00
            )
            await ctx.response.send_message(embed=embed)
            return

        self.playlist.rename_playlist(playlist, new_playlist)
        embed = discord.Embed(
            title=f'プレイリスト名を{new_playlist}に変更しました。',
            color=0xffffff
        )
        await ctx.response.send_message(embed=embed)

    @app_commands.command(name='プレイリスト一覧を表示', description='登録されているプレイリスト一覧を表示します。')
    async def show_playlist(self, ctx: discord.Interaction):
        """プレイリスト一覧を表示"""
        playlist_path = self.config.PLAYLIST_PATH
        lists = [
            os.path.splitext(file)[0]
            for file in os.listdir(playlist_path)
            if file.endswith('.json')
        ]
        logger.debug(f'Playlist Files: {lists}')

        if lists == []:
            embed = discord.Embed(
                title=':warning:登録されているプレイリストが存在しません。',
                color=0xffff00
            )
            await ctx.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title='登録されているプレイリスト一覧を表示します。',
            color=0xffffff
        )
        await ctx.response.send_message(embed=embed)

        embed = self.utils.create_queue_embed(
            lists,
            title='登録されているプレイリスト一覧',
            footer=f'登録されているプレイリスト数:{len(lists)}',
            addPages=True,
            getTitle=False
        )
        await ctx.channel.send(embed=embed)
        logger.info('Show Playlist Command')

    @app_commands.command(name='プレイリストに登録されている曲を表示', description='プレイリストに登録された曲を表示します。')
    @app_commands.describe(playlist='プレイリスト名')
    async def show_music_from_playlist(self, ctx: discord.Interaction, playlist: str):
        """プレイリストの曲一覧を表示"""
        playlist_path = self.config.PLAYLIST_PATH

        if not os.path.exists(f'{playlist_path}{playlist}.json'):
            embed = discord.Embed(
                title=f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。',
                color=0xffff00
            )
            await ctx.response.send_message(embed=embed)
            return

        with open(f'{playlist_path}{playlist}.json', 'r', encoding='utf-8') as f:
            json_list = orjson.loads(f.read())
            embed = discord.Embed(
                title=f'プレイリスト:{playlist}に登録されている曲一覧',
                color=0xffffff
            )
            await ctx.response.send_message(embed=embed)

            embed = self.utils.create_queue_embed(
                json_list['urls'],
                title=f'プレイリスト:{playlist}の曲の一覧',
                footer=f'プレイリストに登録された曲数:{len(json_list["urls"])}曲',
                addPages=True
            )
            await ctx.channel.send(embed=embed)

    @app_commands.command(name='プレイリストのロックを変更', description='プレイリストの編集ロックを変更します。')
    @app_commands.describe(playlist='プレイリスト名', locked='プレイリストの編集を禁止する')
    async def change_playlist_lock(
        self,
        ctx: discord.Interaction,
        playlist: str,
        locked: bool
    ):
        """プレイリストのロック設定を変更"""
        playlist_path = self.config.PLAYLIST_PATH

        if not os.path.exists(f'{playlist_path}{playlist}.json'):
            embed = discord.Embed(
                title=f':warning:プレイリスト{playlist}が存在しません、名前が合っているか確認してください。',
                color=0xffff00
            )
            await ctx.response.send_message(embed=embed)
            return

        await ctx.response.defer()

        with open(f'{playlist_path}{playlist}.json', 'r', encoding='utf-8') as f:
            json_list = orjson.loads(f.read())

        if ctx.user.id not in json_list['owner']:
            embed = discord.Embed(
                title=':warning:プレイリストの編集ロックを変更できるのは作成者のみです。',
                color=0xff0000
            )
            await ctx.followup.send(embed=embed)
            return

        json_list['locked'] = locked
        with open(f'{playlist_path}{playlist}.json', 'w', encoding='utf-8') as f:
            f.write(orjson.dumps(json_list, option=orjson.OPT_INDENT_2).decode('utf-8'))

        result = 'ロックを有効化しました。' if locked else 'ロックを無効化しました。'
        embed = discord.Embed(
            title=f'プレイリスト:{playlist}の編集{result}',
            color=0xffffff
        )
        await ctx.followup.send(embed=embed)

    @app_commands.command(name='プレイリストを結合する', description='指定した2つのプレイリストを結合します。')
    @app_commands.describe(
        parent_playlist='結合先の親プレイリスト名',
        child_playlist='結合する子プレイリスト名'
    )
    async def join_playlist(
        self,
        ctx: discord.Interaction,
        parent_playlist: str,
        child_playlist: str
    ):
        """プレイリストを結合"""
        playlist_path = self.config.PLAYLIST_PATH

        if parent_playlist == child_playlist:
            embed = discord.Embed(title=':warning:同じプレイリスト同士は結合できません。', color=0xffff00)
            await ctx.response.send_message(embed=embed)
            return

        if not (os.path.exists(f'{playlist_path}{parent_playlist}.json') and
                os.path.exists(f'{playlist_path}{child_playlist}.json')):
            embed = discord.Embed(
                title=f':warning:プレイリスト{parent_playlist}または{child_playlist}が存在しません、名前が合っているか確認してください。',
                color=0xff0000
            )
            await ctx.response.send_message(embed=embed)
            return

        await ctx.response.defer()

        with open(f'{playlist_path}{parent_playlist}.json', 'r', encoding='utf-8') as f:
            parent_json = orjson.loads(f.read())

        if parent_json['locked']:
            if ctx.user.id not in parent_json['owner']:
                embed = discord.Embed(
                    title=f':warning:プレイリスト{parent_playlist}は編集が禁止されています。',
                    color=0xffff00
                )
                await ctx.followup.send(embed=embed)
                return

        with open(f'{playlist_path}{child_playlist}.json', 'r', encoding='utf-8') as f:
            child_json = orjson.loads(f.read())

        skip_urls = []

        for url in child_json['urls'][:]:
            if url not in parent_json['urls']:
                parent_json['urls'].append(url)
            else:
                child_json['urls'].remove(url)
                skip_urls.append(url)

        if len(skip_urls) != 0:
            embed = discord.Embed(title=':warning:登録済みのURLはスキップされました。', color=0xffff00)
            await ctx.channel.send(embed=embed)

        if len(child_json['urls']) == 0:
            embed = discord.Embed(
                title=':warning:プレイリストに新たに登録できるURLがありませんでした。',
                color=0xffffff
            )
            await ctx.followup.send(embed=embed)
            return

        json_list = {
            'owner': parent_json['owner'],
            'locked': parent_json['locked'],
            'urls': parent_json['urls']
        }
        with open(f'{playlist_path}{parent_playlist}.json', 'w', encoding='utf-8') as f:
            f.write(orjson.dumps(json_list, option=orjson.OPT_INDENT_2).decode('utf-8'))

        embed = discord.Embed(
            title=f'プレイリスト:{child_playlist}を{parent_playlist}に結合しました。',
            color=0xffffff
        )
        await ctx.followup.send(embed=embed)

        embed = self.utils.create_queue_embed(
            child_json['urls'],
            title=f'プレイリスト:{parent_playlist}に追加された曲の一覧',
            footer=f'プレイリストに登録された曲数:{len(child_json["urls"])}曲',
            addPages=True
        )
        await ctx.channel.send(embed=embed)


async def setup(bot: commands.Bot):
    """Cogのセットアップ"""
    pass
