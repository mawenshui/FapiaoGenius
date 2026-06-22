"""规则文件管理器"""

import json
import uuid
from pathlib import Path
from typing import Optional
from models.parse_rule import ParseRule
from core.app_config import app_config
from core.logger import logger


class RuleManager:
    """规则文件管理器"""
    
    def __init__(self):
        self.rules_dir = app_config.rules_dir
    
    def load_all(self) -> list[ParseRule]:
        """加载所有规则文件"""
        rules = []
        
        if not self.rules_dir.exists():
            logger.warning(f"规则目录不存在: {self.rules_dir}")
            return rules
        
        for rule_file in self.rules_dir.glob("*.json"):
            try:
                rule = self.load(rule_file)
                if rule:
                    rules.append(rule)
            except Exception as e:
                logger.error(f"加载规则文件失败: {rule_file}, 错误: {e}")
        
        logger.info(f"已加载 {len(rules)} 个规则文件")
        return rules
    
    def load(self, file_path: Path) -> Optional[ParseRule]:
        """加载单个规则文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return ParseRule.from_json(content)
        except Exception as e:
            logger.error(f"读取规则文件失败: {file_path}, 错误: {e}")
            return None
    
    def save(self, rule: ParseRule) -> str:
        """
        保存规则到文件
        
        Args:
            rule: 规则对象
            
        Returns:
            str: 规则文件路径
        """
        # 确保目录存在
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        
        # 如果没有 ID，生成一个
        if not rule.id:
            rule.id = str(uuid.uuid4())
        
        # 设置时间戳
        rule.set_timestamps()
        
        # 生成文件名
        safe_name = rule.rule_name.replace(' ', '_').replace('/', '_')
        file_path = self.rules_dir / f"{rule.id}_{safe_name}.json"
        
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(rule.to_json())
        
        logger.info(f"规则已保存: {file_path}")
        return str(file_path)
    
    def delete(self, rule_id: str) -> bool:
        """删除规则文件"""
        for rule_file in self.rules_dir.glob(f"{rule_id}_*.json"):
            try:
                rule_file.unlink()
                logger.info(f"规则已删除: {rule_file}")
                return True
            except Exception as e:
                logger.error(f"删除规则文件失败: {rule_file}, 错误: {e}")
        return False
    
    def get_by_id(self, rule_id: str) -> Optional[ParseRule]:
        """根据 ID 获取规则"""
        for rule_file in self.rules_dir.glob(f"{rule_id}_*.json"):
            return self.load(rule_file)
        return None
    
    def exists(self, rule_id: str) -> bool:
        """检查规则是否存在"""
        return any(self.rules_dir.glob(f"{rule_id}_*.json"))


# 全局规则管理器实例
rule_manager = RuleManager()

