# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import subprocess
import sys
import requests
from typing import Optional, Tuple

logger = logging.getLogger('PlayAudio')


class UpdateManager:
    """パッケージ更新管理クラス
    yt-dlpとdiscord.pyの更新機能を提供
    """
    
    # 更新を許可するパッケージリスト
    ALLOWED_PACKAGES = ['yt-dlp', 'discord.py']
    
    def __init__(self):
        """UpdateManager初期化"""
        self.logger = logger
        self.logger.debug('🔧 UpdateManager クラスが初期化されました')
    
    def get_current_version(self, package_name: str) -> Optional[str]:
        """現在インストールされているパッケージのバージョンを取得
        
        Args:
            package_name (str): パッケージ名
            
        Returns:
            Optional[str]: バージョン文字列、取得失敗時はNone
        """
        if package_name not in self.ALLOWED_PACKAGES:
            self.logger.warning(f'⚠️ 許可されていないパッケージ: {package_name}')
            return None
        
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'show', package_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        version = line.split(':', 1)[1].strip()
                        self.logger.debug(f'📦 {package_name} 現在のバージョン: {version}')
                        return version
            else:
                self.logger.warning(f'⚠️ {package_name} の情報取得に失敗しました')
                return None
                
        except subprocess.TimeoutExpired:
            self.logger.error(f'❌ {package_name} バージョン取得がタイムアウトしました')
            return None
        except Exception as e:
            self.logger.error(f'❌ {package_name} バージョン取得エラー: {e}')
            return None
    
    async def get_latest_version(self, package_name: str) -> Optional[str]:
        """PyPIから最新バージョンを取得
        
        Args:
            package_name (str): パッケージ名
            
        Returns:
            Optional[str]: 最新バージョン文字列、取得失敗時はNone
        """
        if package_name not in self.ALLOWED_PACKAGES:
            self.logger.warning(f'⚠️ 許可されていないパッケージ: {package_name}')
            return None
        
        try:
            # discord.pyの場合はdiscord-pyでPyPIにアクセス
            pypi_name = 'discord-py' if package_name == 'discord.py' else package_name
            url = f'https://pypi.org/pypi/{pypi_name}/json'
            
            self.logger.debug(f'🔍 {package_name} の最新バージョンをPyPIから取得中...')
            
            # 非同期でHTTPリクエストを実行
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.get(url, timeout=15)
            )
            
            if response.status_code == 200:
                data = response.json()
                latest_version = data['info']['version']
                self.logger.debug(f'📦 {package_name} 最新バージョン: {latest_version}')
                return latest_version
            else:
                self.logger.error(f'❌ {package_name} 最新バージョン取得失敗: HTTP {response.status_code}')
                return None
                
        except Exception as e:
            self.logger.error(f'❌ {package_name} 最新バージョン取得エラー: {e}')
            return None
    
    async def check_update_available(self, package_name: str) -> Tuple[Optional[str], Optional[str], bool]:
        """パッケージの更新が利用可能かチェック
        
        Args:
            package_name (str): パッケージ名
            
        Returns:
            Tuple[Optional[str], Optional[str], bool]: (現在版, 最新版, 更新可能)
        """
        current_version = self.get_current_version(package_name)
        latest_version = await self.get_latest_version(package_name)
        
        if current_version and latest_version:
            update_available = current_version != latest_version
            self.logger.info(f'🔍 {package_name} 更新チェック - 現在: {current_version}, 最新: {latest_version}, 更新可能: {update_available}')
            return current_version, latest_version, update_available
        else:
            self.logger.warning(f'⚠️ {package_name} のバージョン情報取得に失敗しました')
            return current_version, latest_version, False
    
    async def update_package(self, package_name: str) -> bool:
        """指定されたパッケージを更新
        
        Args:
            package_name (str): パッケージ名
            
        Returns:
            bool: 更新成功時True
        """
        if package_name not in self.ALLOWED_PACKAGES:
            self.logger.error(f'❌ 許可されていないパッケージです: {package_name}')
            return False
        
        try:
            current_version = self.get_current_version(package_name)
            latest_version = await self.get_latest_version(package_name)
            
            self.logger.info(f'🔄 {package_name} 更新開始: {current_version} → {latest_version}')
            
            # pip install --upgrade を実行
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', package_name],
                capture_output=True,
                text=True,
                timeout=300  # 5分タイムアウト
            )
            
            if result.returncode == 0:
                new_version = self.get_current_version(package_name)
                self.logger.info(f'✅ {package_name} 更新完了: {new_version}')
                return True
            else:
                self.logger.error(f'❌ {package_name} 更新失敗: {result.stderr}')
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f'❌ {package_name} 更新がタイムアウトしました（5分）')
            return False
        except Exception as e:
            self.logger.error(f'❌ {package_name} 更新エラー: {e}')
            return False
    
    async def restart_bot(self):
        """Bot を再起動
        現在のプロセスを終了し、新しいプロセスを開始
        """
        self.logger.info('🔄 Bot再起動を実行します...')
        try:
            # 現在のプロセスを新しいプロセスで置き換え
            python = sys.executable
            args = [python] + sys.argv
            
            self.logger.info('🚀 新しいプロセスで Bot を再起動中...')
            os.execv(python, args)
            
        except Exception as e:
            self.logger.critical(f'🚨 Bot再起動に失敗しました: {e}')
            # 再起動に失敗した場合は通常の終了
            sys.exit(1)