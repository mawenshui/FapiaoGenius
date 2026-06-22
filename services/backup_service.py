"""数据备份与恢复服务"""

import os
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from core.logger import logger
from core.app_config import app_config


class BackupService:
    """数据备份与恢复服务"""
    
    BACKUP_VERSION = "1.0"
    
    def create_backup(self, save_path: str) -> dict:
        """
        创建完整备份（数据库 + 规则文件 + 配置）
        
        Returns:
            {'success': bool, 'message': str, 'path': str}
        """
        result = {'success': False, 'message': '', 'path': ''}
        
        try:
            data_dir = Path(app_config.data_dir)
            db_path = Path(app_config.db_path)
            rules_dir = Path(app_config.rules_dir)
            
            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                file_count = 0
                
                # 备份数据库
                if db_path.exists():
                    zf.write(db_path, 'invoices.db')
                    file_count += 1
                
                # 备份规则文件
                if rules_dir.exists():
                    for rule_file in rules_dir.glob("*.json"):
                        zf.write(rule_file, f"rules/{rule_file.name}")
                        file_count += 1
                
                # 备份主题偏好
                theme_file = data_dir / "theme.json"
                if theme_file.exists():
                    zf.write(theme_file, "theme.json")
                    file_count += 1
                
                # 写入备份元信息
                meta = {
                    'version': self.BACKUP_VERSION,
                    'app': 'FapiaoGenius',
                    'created_at': datetime.now().isoformat(),
                    'file_count': file_count,
                }
                import json
                zf.writestr('backup_meta.json', json.dumps(meta, ensure_ascii=False, indent=2))
            
            result['success'] = True
            result['message'] = f"备份完成！\n\n已备份 {file_count} 个文件到:\n{save_path}"
            result['path'] = save_path
            logger.info(f"备份创建成功: {save_path} ({file_count} 文件)")
            
        except Exception as e:
            result['message'] = f"备份失败: {e}"
            logger.error(f"备份创建失败: {e}")
        
        return result
    
    def restore_backup(self, zip_path: str) -> dict:
        """
        从备份恢复数据
        
        Returns:
            {'success': bool, 'message': str}
        """
        result = {'success': False, 'message': ''}
        
        try:
            # 验证备份文件
            with zipfile.ZipFile(zip_path, 'r') as zf:
                names = zf.namelist()
                
                if 'backup_meta.json' not in names:
                    result['message'] = "无效的备份文件：缺少 backup_meta.json"
                    return result
                
                import json
                meta = json.loads(zf.read('backup_meta.json').decode('utf-8'))
                
                if meta.get('app') != 'FapiaoGenius':
                    result['message'] = "无效的备份文件：非智票通备份"
                    return result
                
                # 关闭数据库连接
                from database.connection import db
                db.close()
                
                data_dir = Path(app_config.data_dir)
                db_path = Path(app_config.db_path)
                rules_dir = Path(app_config.rules_dir)
                
                restored = 0
                
                # 恢复数据库
                if 'invoices.db' in names:
                    # 备份当前数据库
                    if db_path.exists():
                        backup_db = db_path.with_suffix('.db.bak')
                        shutil.copy2(db_path, backup_db)
                    
                    zf.extract('invoices.db', data_dir)
                    restored += 1
                
                # 恢复规则文件
                rules_prefix = 'rules/'
                rule_files = [n for n in names if n.startswith(rules_prefix)]
                if rule_files:
                    rules_dir.mkdir(parents=True, exist_ok=True)
                    for rule_file in rule_files:
                        filename = Path(rule_file).name
                        target = rules_dir / filename
                        with zf.open(rule_file) as src, open(target, 'wb') as dst:
                            dst.write(src.read())
                        restored += 1
                
                # 恢复主题偏好
                if 'theme.json' in names:
                    zf.extract('theme.json', data_dir)
                    restored += 1
            
            # 重新初始化数据库连接
            from database.connection import db as db_module
            db_module._connection = None
            
            result['success'] = True
            result['message'] = f"恢复完成！\n\n已恢复 {restored} 个文件。\n\n请重启应用以使更改生效。"
            logger.info(f"备份恢复成功: {restored} 文件")
            
        except zipfile.BadZipFile:
            result['message'] = "无效的备份文件：不是有效的 ZIP 包"
        except Exception as e:
            result['message'] = f"恢复失败: {e}"
            logger.error(f"备份恢复失败: {e}")
        
        return result
    
    def get_default_backup_name(self) -> str:
        """获取默认备份文件名"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"智票通_备份_{timestamp}.zip"


# 全局服务实例
backup_service = BackupService()
