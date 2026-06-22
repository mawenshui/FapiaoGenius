"""文件操作工具函数"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from core.logger import logger
from core.constants import SUPPORTED_EXTENSIONS


def open_file(file_path: str) -> bool:
    """使用系统默认程序打开文件"""
    try:
        if not os.path.exists(file_path):
            logger.warning(f"文件不存在: {file_path}")
            return False
        
        if os.name == 'nt':
            os.startfile(file_path)
        else:
            subprocess.run(['xdg-open', file_path], check=True)
        
        logger.debug(f"已打开文件: {file_path}")
        return True
    except Exception as e:
        logger.error(f"打开文件失败: {file_path}, 错误: {e}")
        return False


def get_file_extension(file_path: str) -> str:
    """获取文件扩展名（小写）"""
    return Path(file_path).suffix.lower()


def is_supported_file(file_path: str) -> bool:
    """检查文件是否为支持的格式"""
    ext = get_file_extension(file_path)
    return ext in SUPPORTED_EXTENSIONS


def get_files_from_folder(folder_path: str) -> list[str]:
    """从文件夹获取所有支持的文件路径"""
    files = []
    folder = Path(folder_path)
    
    if not folder.exists():
        logger.warning(f"文件夹不存在: {folder_path}")
        return files
    
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(str(p) for p in folder.rglob(f"*{ext}"))
    
    logger.debug(f"从文件夹 {folder_path} 发现 {len(files)} 个文件")
    return sorted(files)


def get_file_name(file_path: str) -> str:
    """获取文件名（不含路径）"""
    return Path(file_path).name


def get_file_size_str(file_path: str) -> str:
    """获取文件大小的可读字符串"""
    try:
        size = os.path.getsize(file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    except OSError:
        return "未知"
