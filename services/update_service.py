"""自动更新服务 — GitHub Release 检查与下载"""

import json
import urllib.request
import ssl
from core.logger import logger


class UpdateService:
    """自动更新服务"""
    
    GITHUB_REPO = "mawenshui/FapiaoGenius"
    API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    
    def check_update(self, current_version: str) -> dict:
        """
        检查是否有新版本
        
        Returns:
            {'has_update': bool, 'version': str, 'download_url': str, 'changelog': str}
        """
        result = {
            'has_update': False,
            'version': '',
            'download_url': '',
            'changelog': '',
            'error': None
        }
        
        try:
            # 创建不验证SSL证书的context（某些环境需要）
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(
                self.API_URL,
                headers={'User-Agent': 'FapiaoGenius-Updater'}
            )
            
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            
            latest_version = data.get('tag_name', '').lstrip('v')
            result['version'] = latest_version
            result['changelog'] = data.get('body', '')
            
            # 查找 Windows 下载链接
            for asset in data.get('assets', []):
                name = asset.get('name', '').lower()
                if name.endswith(('.exe', '.msi', '.zip')) and 'win' in name:
                    result['download_url'] = asset.get('browser_download_url', '')
                    break
            
            # 如果没有找到特定 Windows 包，取第一个资产
            if not result['download_url'] and data.get('assets'):
                result['download_url'] = data['assets'][0].get('browser_download_url', '')
            
            # 比较版本
            result['has_update'] = self._compare_versions(latest_version, current_version) > 0
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"检查更新失败: {e}")
        
        return result
    
    def download_update(self, url: str, save_path: str, progress_callback=None) -> bool:
        """
        下载更新包
        
        Args:
            url: 下载链接
            save_path: 保存路径
            progress_callback: 进度回调 (downloaded, total)
        """
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url, headers={'User-Agent': 'FapiaoGenius-Updater'})
            
            with urllib.request.urlopen(req, context=ctx) as resp:
                total = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                block_size = 8192
                
                with open(save_path, 'wb') as f:
                    while True:
                        chunk = resp.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total:
                            progress_callback(downloaded, total)
            
            logger.info(f"更新包已下载: {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"下载更新失败: {e}")
            return False
    
    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """比较版本号: v1 > v2 返回正数, v1 < v2 返回负数, 相等返回 0"""
        def parse(v):
            parts = []
            for p in v.split('.'):
                try:
                    parts.append(int(p))
                except ValueError:
                    parts.append(0)
            return parts
        
        p1, p2 = parse(v1), parse(v2)
        # 补齐长度
        while len(p1) < len(p2):
            p1.append(0)
        while len(p2) < len(p1):
            p2.append(0)
        
        for a, b in zip(p1, p2):
            if a != b:
                return a - b
        return 0


# 全局服务实例
update_service = UpdateService()
