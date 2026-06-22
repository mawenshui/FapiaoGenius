"""规则匹配与管理服务"""

from typing import Optional
from models.parse_rule import ParseRule
from config.rule_manager import rule_manager
from database.rule_dao import rule_dao
from core.logger import logger


class RuleService:
    """规则服务"""
    
    def __init__(self):
        self._rules: list[ParseRule] = []
        self._loaded = False
    
    def load_rules(self):
        """加载所有规则（文件 + 数据库）"""
        self._rules = []
        
        # 从文件加载
        file_rules = rule_manager.load_all()
        self._rules.extend(file_rules)
        
        # 从数据库加载（AI 学习的规则）
        db_rules = rule_dao.get_all()
        existing_ids = {r.id for r in self._rules}
        for rule in db_rules:
            if rule.id not in existing_ids:
                self._rules.append(rule)
        
        self._loaded = True
        logger.info(f"已加载 {len(self._rules)} 个规则")
    
    def get_all_rules(self) -> list[ParseRule]:
        """获取所有规则"""
        if not self._loaded:
            self.load_rules()
        return self._rules
    
    def match_rule(self, text: str, file_format: str) -> Optional[ParseRule]:
        """
        根据文本内容匹配最佳规则
        
        Args:
            text: 文件文本内容
            file_format: 文件格式（pdf/ofd）
            
        Returns:
            ParseRule: 匹配的规则，无匹配返回 None
        """
        if not self._loaded:
            self.load_rules()
        
        best_match = None
        best_score = 0
        best_total_len = 0  # 平局时比较总匹配关键字长度

        for rule in self._rules:
            if rule.file_format != file_format:
                continue

            score, total_len = self._calculate_match_score(text, rule)
            # 优先高分；同分时选总关键字长度更大的（更具体的规则）
            if score > best_score or (score == best_score and total_len > best_total_len):
                best_score = score
                best_total_len = total_len
                best_match = rule

        if best_match:
            logger.debug(f"匹配到规则: {best_match.rule_name}, 得分: {best_score}")
        
        return best_match
    
    def _calculate_match_score(self, text: str, rule: ParseRule) -> tuple:
        """
        计算规则匹配得分

        策略：使用关键字长度作为权重（长关键字更具体），
        避免「电子发票」这类宽泛关键词导致规则误匹配。

        Returns:
            (score, total_matched_len): 得分 和 已匹配关键字总长度（用于平局裁决）
        """
        score = 0
        total_len = 0

        for keyword in rule.match_keywords:
            if keyword in text:
                # 用关键字长度加权，避免短泛词（如"增值税"3字）压倒长精确词
                score += len(keyword) * 3
                total_len += len(keyword)

        return score, total_len
    
    def save_rule(self, rule: ParseRule) -> str:
        """
        保存规则（同时保存到文件和数据库）
        
        Args:
            rule: 规则对象
            
        Returns:
            str: 规则文件路径
        """
        # 保存到文件
        file_path = rule_manager.save(rule)
        
        # 保存到数据库
        rule_dao.insert(rule)
        
        # 重新加载
        self.load_rules()
        
        return file_path
    
    def delete_rule(self, rule_id: str) -> bool:
        """删除规则"""
        # 从文件删除
        rule_manager.delete(rule_id)
        
        # 从数据库删除
        rule_dao.delete(rule_id)
        
        # 重新加载
        self.load_rules()
        
        return True
    
    def get_by_id(self, rule_id: str) -> Optional[ParseRule]:
        """根据 ID 获取规则"""
        for rule in self._rules:
            if rule.id == rule_id:
                return rule
        return None


# 全局规则服务实例
rule_service = RuleService()
