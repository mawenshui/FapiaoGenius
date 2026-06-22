"""配置导入导出服务 — 多用户配置迁移"""

import json
import zipfile
import shutil
from pathlib import Path
from core.logger import logger
from core.app_config import app_config


class ConfigTransferService:
    """配置导入导出服务"""
    
    EXPORT_VERSION = "1.0"
    
    def export_config(self, save_path: str) -> dict:
        """
        导出配置包（ZIP 格式）
        
        包含：
        - AI 配置
        - 主题偏好
        - 自定义解析规则
        """
        result = {'success': False, 'message': '', 'path': ''}
        
        try:
            data_dir = Path(app_config.data_dir)
            export_data = {
                'version': self.EXPORT_VERSION,
                'app': 'FapiaoGenius',
            }
            
            # 1. 导出 AI 配置
            from database.config_dao import config_dao
            ai_config = config_dao.get()
            export_data['ai_config'] = {
                'api_url': ai_config.api_url,
                'model_name': ai_config.model_name,
                # 不导出 api_key（安全考虑）
            }
            
            # 2. 导出主题偏好
            from utils.theme_manager import ThemeManager
            export_data['theme'] = ThemeManager.get_current_theme()
            
            # 3. 收集自定义规则
            rules_dir = Path(app_config.rules_dir)
            custom_rules = []
            if rules_dir.exists():
                for rule_file in rules_dir.glob("*.json"):
                    if not rule_file.name.startswith("builtin_"):
                        try:
                            with open(rule_file, 'r', encoding='utf-8') as f:
                                custom_rules.append({
                                    'filename': rule_file.name,
                                    'content': json.load(f)
                                })
                        except Exception as e:
                            logger.warning(f"导出规则失败 {rule_file.name}: {e}")
            export_data['custom_rules'] = custom_rules
            
            # 写入 ZIP
            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 写入主配置文件
                zf.writestr('config.json', json.dumps(export_data, ensure_ascii=False, indent=2))
            
            result['success'] = True
            result['message'] = f"配置已导出到:\n{save_path}\n\n包含:\n- AI 配置\n- 主题偏好\n- {len(custom_rules)} 个自定义规则"
            result['path'] = save_path
            logger.info(f"配置导出成功: {save_path}")
            
        except Exception as e:
            result['message'] = f"导出失败: {e}"
            logger.error(f"配置导出失败: {e}")
        
        return result
    
    def import_config(self, zip_path: str) -> dict:
        """
        导入配置包
        
        返回导入结果摘要
        """
        result = {'success': False, 'message': '', 'imported_items': []}
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # 读取主配置
                if 'config.json' not in zf.namelist():
                    result['message'] = "无效的配置包：缺少 config.json"
                    return result
                
                config_data = json.loads(zf.read('config.json').decode('utf-8'))
            
            # 验证
            if config_data.get('app') != 'FapiaoGenius':
                result['message'] = "无效的配置包：非智票通配置"
                return result
            
            imported = []
            
            # 1. 导入 AI 配置
            if 'ai_config' in config_data:
                from database.config_dao import config_dao
                from models.ai_config import AIConfig
                ai_data = config_data['ai_config']
                current = config_dao.get()
                current.api_url = ai_data.get('api_url', current.api_url)
                current.model_name = ai_data.get('model_name', current.model_name)
                config_dao.save(current)
                imported.append("AI 配置")
            
            # 2. 导入主题
            if 'theme' in config_data:
                from utils.theme_manager import ThemeManager
                theme = config_data['theme']
                ThemeManager.save_theme(theme)
                imported.append(f"主题: {theme}")
            
            # 3. 导入自定义规则
            rules_dir = Path(app_config.rules_dir)
            rules_dir.mkdir(parents=True, exist_ok=True)
            for rule in config_data.get('custom_rules', []):
                filename = rule.get('filename', '')
                content = rule.get('content', {})
                if filename and content:
                    rule_path = rules_dir / filename
                    with open(rule_path, 'w', encoding='utf-8') as f:
                        json.dump(content, f, ensure_ascii=False, indent=2)
                    imported.append(f"规则: {filename}")
            
            result['success'] = True
            result['message'] = f"导入成功！\n\n已导入:\n" + "\n".join(f"  ✓ {item}" for item in imported)
            result['imported_items'] = imported
            logger.info(f"配置导入成功: {len(imported)} 项")
            
        except zipfile.BadZipFile:
            result['message'] = "无效的文件：不是有效的 ZIP 包"
        except Exception as e:
            result['message'] = f"导入失败: {e}"
            logger.error(f"配置导入失败: {e}")
        
        return result


# 全局服务实例
config_transfer_service = ConfigTransferService()
