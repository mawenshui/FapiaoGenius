"""加密工具函数"""

import os
import base64
from typing import Optional

from core.logger import logger


def _get_key() -> bytes:
    """获取加密密钥（基于机器特征）"""
    # 使用简单的密钥派生（基于用户名和固定盐值）
    username = os.environ.get('USERNAME', os.environ.get('USER', 'default'))
    salt = b'ai_fapiao_salt_2024'
    key_material = f"{username}_{salt.decode()}".encode()
    
    # 简单哈希到 32 字节
    import hashlib
    key = hashlib.sha256(key_material).digest()
    return base64.urlsafe_b64encode(key)


def encrypt_key(plain_text: str) -> str:
    """加密字符串"""
    if not plain_text:
        return ""
    
    try:
        from cryptography.fernet import Fernet
        
        key = _get_key()
        f = Fernet(key)
        encrypted = f.encrypt(plain_text.encode('utf-8'))
        return encrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"加密失败: {e}")
        # 降级为 base64 编码
        return base64.b64encode(plain_text.encode('utf-8')).decode('utf-8')


def decrypt_key(encrypted_text: str) -> str:
    """解密字符串"""
    if not encrypted_text:
        return ""
    
    try:
        from cryptography.fernet import Fernet
        
        key = _get_key()
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_text.encode('utf-8'))
        return decrypted.decode('utf-8')
    except Exception as e:
        logger.debug(f"Fernet 解密失败，尝试 base64: {e}")
        try:
            # 降级尝试 base64 解码
            return base64.b64decode(encrypted_text.encode('utf-8')).decode('utf-8')
        except Exception:
            logger.warning("解密失败，返回原文")
            return encrypted_text
