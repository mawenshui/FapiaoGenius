"""AI 智能识别页面 — 批量 AI 发票识别与学习"""

import os
import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QComboBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QMessageBox, QAbstractItemView, QSplitter, QCheckBox,
    QScrollArea, QFrame, QSizePolicy, QStyledItemDelegate, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QApplication

from services.ai_service import ai_service
from services.rule_service import rule_service
from database.invoice_dao import invoice_dao
from models.invoice import Invoice
from models.parse_rule import ParseRule
from core.logger import logger
from utils.file_utils import is_supported_file, get_files_from_folder
from utils.validators import normalize_date, parse_amount


class BatchAIWorker(QThread):
    """批量 AI 分析工作线程"""
    progress = pyqtSignal(int, int, str)       # current, total, filename
    file_done = pyqtSignal(str, object)        # file_path, result(dict) or Exception
    all_done = pyqtSignal()

    def __init__(self, file_paths: list):
        super().__init__()
        self.file_paths = file_paths
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        total = len(self.file_paths)
        logger.info(f"[批量AI] ===== 开始批量识别, 共 {total} 个文件 =====")
        for i, file_path in enumerate(self.file_paths):
            if self._cancelled:
                logger.info(f"[批量AI] 用户取消, 已处理 {i}/{total} 个文件")
                break
            name = Path(file_path).name
            self.progress.emit(i + 1, total, name)
            logger.info(f"[批量AI] ({i+1}/{total}) 开始分析: {name}")
            try:
                result = ai_service.analyze_invoice(file_path)
                logger.info(
                    f"[批量AI] ({i+1}/{total}) ✓ 成功: {name}, "
                    f"号码={result.get('invoice_number','')}, "
                    f"日期={result.get('invoice_date','')}, "
                    f"购买方={result.get('buyer_name','')}, "
                    f"销售方={result.get('seller_name','')}, "
                    f"不含税={result.get('amount_without_tax',0)}, "
                    f"税额={result.get('tax_amount',0)}, "
                    f"价税合计={result.get('total_amount',0)}, "
                    f"类型={result.get('invoice_type','')}, "
                    f"业务={result.get('business_type','')}, "
                    f"置信度={result.get('confidence','')}"
                )
                if result.get('validation_warning'):
                    logger.warning(
                        f"[批量AI] ({i+1}/{total}) ⚠ 金额校验警告: {name}, "
                        f"{result['validation_warning']}"
                    )
                self.file_done.emit(file_path, result)
            except Exception as e:
                logger.error(
                    f"[批量AI] ({i+1}/{total}) ✗ 失败: {name}, "
                    f"错误类型={type(e).__name__}, 错误={e}"
                )
                self.file_done.emit(file_path, e)
        logger.info(f"[批量AI] ===== 批量识别线程结束 =====")
        self.all_done.emit()


class BatchLearnWorker(QThread):
    """批量 AI 学习工作线程"""
    progress = pyqtSignal(int, int, str)       # current, total, filename
    file_done = pyqtSignal(str, bool, str)     # file_path, success, message
    learn_log = pyqtSignal(str, str)           # message, tag — 实时学习过程日志
    all_done = pyqtSignal()

    def __init__(self, items: list):
        """
        Args:
            items: [(file_path, data_dict), ...] 每个元素是文件路径和 AI 识别结果
        """
        super().__init__()
        self.items = items
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        import uuid
        from datetime import datetime

        total = len(self.items)
        logger.info(f"[批量学习] ===== 开始批量学习, 共 {total} 个文件 =====")
        for i, (file_path, data) in enumerate(self.items):
            if self._cancelled:
                logger.info(f"[批量学习] 用户取消, 已处理 {i}/{total} 个文件")
                break
            name = Path(file_path).name
            self.progress.emit(i + 1, total, name)

            try:
                # 1. 规则名称：销售方名称 > 发票号码 > 默认
                seller_name = str(data.get('seller_name', '')).strip()
                invoice_number = str(data.get('invoice_number', '')).strip()
                if seller_name:
                    rule_name = seller_name
                elif invoice_number:
                    rule_name = invoice_number
                else:
                    rule_name = "未命名规则"
                logger.info(
                    f"[批量学习] ({i+1}/{total}) 开始: {name}, "
                    f"规则名={rule_name}, 发票号={invoice_number}"
                )

                # 2. 重试循环：最多 5 次，直到规则提取结果与 AI 识别一致
                error_context = ""
                success = False
                last_diff = ""
                last_failed_configs = ""  # 累积所有失败正则历史

                for attempt in range(1, 6):
                    if self._cancelled:
                        logger.info(f"[批量学习] ({i+1}/{total}) 第{attempt}次尝试: 用户取消")
                        self.learn_log.emit(
                            f"({i+1}/{total}) {name} — 第{attempt}次: 用户取消",
                            "warn"
                        )
                        break

                    log_prefix = f"[批量学习] ({i+1}/{total})"
                    logger.info(
                        f"{log_prefix} 第{attempt}/5次尝试: {name}"
                        + (" (修正模式)" if error_context else "")
                    )
                    self.learn_log.emit(
                        f"({i+1}/{total}) {name} — 第{attempt}/5次尝试"
                        + (" (修正模式)" if error_context else ""),
                        "step"
                    )

                    # 调用 AI 学习格式
                    t_start = datetime.now()
                    result = ai_service.learn_format(
                        file_path, error_context=error_context
                    )
                    elapsed = (datetime.now() - t_start).total_seconds()
                    logger.info(
                        f"[批量学习] ({i+1}/{total}) 第{attempt}次: "
                        f"AI 返回耗时 {elapsed:.1f}s"
                    )

                    rule_name_ai = result.get('rule_name', '')
                    match_keywords = result.get('match_keywords', [])
                    extraction_config = result.get('extraction_config', {})
                    logger.debug(
                        f"[批量学习] ({i+1}/{total}) 第{attempt}次: "
                        f"AI建议规则名={rule_name_ai}, "
                        f"关键词={match_keywords}, "
                        f"提取字段={list(extraction_config.keys())}"
                    )
                    # 记录每个字段的正则
                    for fld, pat in extraction_config.items():
                        pat_str = pat if isinstance(pat, str) else str(pat)
                        logger.debug(
                            f"[批量学习] ({i+1}/{total}) 第{attempt}次: "
                            f"  字段[{fld}] regex={pat_str[:120]}{'...' if len(pat_str)>120 else ''}"
                        )

                    if not extraction_config:
                        error_context = "AI 未返回有效的 extraction_config"
                        logger.warning(
                            f"{log_prefix} 第{attempt}次: "
                            f"✗ 无extraction_config, 准备重试"
                        )
                        self.learn_log.emit(
                            f"({i+1}/{total}) {name} — 第{attempt}次 ✗ 未生成规则, 重试中…",
                            "warn"
                        )
                        continue

                    # 用规则解析文件，对比 AI 识别结果
                    parsed = self._parse_with_rule(file_path, extraction_config)
                    logger.debug(
                        f"[批量学习] ({i+1}/{total}) 第{attempt}次: "
                        f"规则解析结果={json.dumps(parsed, ensure_ascii=False, default=str)}"
                    )

                    match_result = self._compare_results(data, parsed)

                    if match_result["match"]:
                        # 匹配成功！保存规则
                        rule = ParseRule(
                            id=f"ai_learned_{uuid.uuid4().hex[:8]}",
                            rule_name=rule_name,
                            file_format=Path(file_path).suffix.lower().lstrip('.'),
                            match_keywords=match_keywords,
                            extraction_config=extraction_config,
                            required_fields=["invoice_number", "invoice_date", "total_amount"],
                            created_at=datetime.now().isoformat(),
                            updated_at=datetime.now().isoformat(),
                            is_builtin=False,
                        )
                        rule_service.save_rule(rule)

                        msg = f"规则 '{rule_name}' 已保存（第{attempt}次尝试）"
                        logger.info(
                            f"[批量学习] ({i+1}/{total}) ✓ 成功: {name}, "
                            f"规则名={rule_name}, ID={rule.id}, 尝试={attempt}"
                        )
                        self.file_done.emit(file_path, True, msg)
                        success = True
                        break
                    else:
                        # 不匹配，构建增强的 error_context（包含失败正则和原因分析）
                        last_diff = match_result["diff"]
                        current_fail_info = self._build_error_context(
                            data, parsed, extraction_config
                        )
                        last_failed_configs += (
                            f"\n--- 第{attempt}次尝试 ---\n{current_fail_info}"
                        )
                        error_context = (
                            f"以下字段的正则表达式未能正确提取：\n\n"
                            f"{current_fail_info}\n\n"
                            f"【历史失败正则（已证明无效，请勿重复使用）】\n"
                            f"{last_failed_configs}\n\n"
                            f"请务必采用与之前不同的策略修正正则。"
                        )
                        logger.warning(
                            f"{log_prefix} 第{attempt}次 ✗ 不匹配: {name}\n"
                            f"  差异详情:\n{last_diff}"
                        )
                        # 发射到 UI 学习过程面板
                        ui_msg = f"({i+1}/{total}) {name} — 第{attempt}次 ✗ 不匹配"
                        self.learn_log.emit(ui_msg, "error")
                        # 差异详情分行展示
                        for diff_line in last_diff.split('\n'):
                            if diff_line.strip():
                                self.learn_log.emit(f"    {diff_line.strip()}", "warn")

                if not success:
                    msg = f"5次重试后仍无法匹配"
                    if last_diff:
                        msg += f": {last_diff[:80]}"
                    logger.error(
                        f"[批量学习] ({i+1}/{total}) ✗✗ 最终失败: {name}, {msg}"
                    )
                    self.file_done.emit(file_path, False, msg)

            except Exception as e:
                logger.error(
                    f"[批量学习] ({i+1}/{total}) ✗ 异常: {name}, "
                    f"错误类型={type(e).__name__}, 错误={e}"
                )
                self.file_done.emit(file_path, False, str(e))

        logger.info(f"[批量学习] ===== 批量学习线程结束 =====")
        self.all_done.emit()

    @staticmethod
    def _parse_with_rule(file_path: str, extraction_config: dict) -> dict:
        """
        使用 extraction_config 中的正则从文件中提取字段值

        extraction_config 格式: {field: regex_string}
        每个正则必须包含捕获组。
        """
        import re

        text = ai_service._extract_text_for_ai(file_path)
        if not text:
            return {}

        result = {}
        for field, pattern in extraction_config.items():
            if not pattern:
                result[field] = ""
                continue

            # 兼容旧格式
            if isinstance(pattern, dict):
                pattern = pattern.get('pattern', '')
            if not pattern:
                result[field] = ""
                continue

            value = BatchLearnWorker._try_regex(pattern, text, re.DOTALL)

            # 名称字段：修复缺失的闭合全角括号
            # AI正则常匹配 "XX（个体工商户" 而漏掉末尾的 ）
            if value and field in ('buyer_name', 'seller_name'):
                if '（' in value and not value.endswith('）'):
                    # 在原文本中查找 value 后紧跟 ）的位置
                    escaped = re.escape(value)
                    m = re.search(escaped + '([）])', text)
                    if m:
                        value += '）'

            # 日期字段标准化
            if value and field == 'invoice_date':
                value = BatchLearnWorker._normalize_date(value)

            # 名称字段智能回退（含银行名检测 + 买卖方同名检测）
            if field in ('buyer_name', 'seller_name'):
                # 检测是否为银行/金融机构名称
                bank_keywords = ['银行', '支行', '分行', '信用社', '分理处', '营业部']
                is_bank = any(kw in value for kw in bank_keywords) if value else False
                # 检测 seller_name 是否与 buyer_name 相同（正则误匹配）
                buyer_val = result.get('buyer_name', '')
                is_same_as_buyer = (
                    field == 'seller_name' and value
                    and buyer_val and value == buyer_val
                )
                if not value or len(value) <= 2 or is_bank or is_same_as_buyer:
                    value = BatchLearnWorker._extract_company_name(text, field)

            # 税额智能回退
            if field == 'tax_amount' and value:
                amount_val = result.get('amount_without_tax', '')
                if amount_val and value == amount_val:
                    value = BatchLearnWorker._extract_tax_amount(text, extraction_config)

            # 价税合计智能回退
            if field == 'total_amount' and value:
                try:
                    if float(value) < 10:
                        value = BatchLearnWorker._extract_total_amount(text)
                except ValueError:
                    value = BatchLearnWorker._extract_total_amount(text)

            result[field] = value if value else ""

        return result

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """将中文日期格式标准化为 ISO YYYY-MM-DD"""
        import re
        # 匹配: 2026年05月18日 或 2026年5月8日 → 2026-05-18
        m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', date_str)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        # 匹配: 2026-05-18 或 2026/05/18（已为标准格式）
        m = re.match(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_str)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        # 无法识别，返回原值
        return date_str

    @staticmethod
    def _extract_company_name(text: str, field: str) -> str:
        """
        智能提取公司/商户名称

        当正则无法正确提取名称时，使用公司名称模式匹配。
        支持多种公司类型后缀：有限公司、个体工商户、经营部等。
        """
        import re

        # 银行/金融机构关键词（必须排除）
        bank_keywords = [
            '银行', '支行', '分行', '信用社', '分理处',
            '营业部', '村镇银行', '商业银行', '信用合作'
        ]

        # 按文本位置收集所有候选名称（用 start 位置排序）
        candidates = []  # [(start_pos, name), ...]

        # 模式1: 标准公司名（以"公司"结尾）
        for m in re.finditer(
            r'[\u4e00-\u9fa5（）]{4,}'
            r'(?:有限|股份|集团|责任|合伙|独资)'
            r'[\u4e00-\u9fa5（）]*公司',
            text
        ):
            candidates.append((m.start(), m.group()))

        # 模式2: 个体工商户（含可选的闭合全角括号）
        # 实际发票中公司名称格式为 "XX（个体工商户）"，正则需捕获闭合的 ）
        for m in re.finditer(
            r'[\u4e00-\u9fa5（）]{4,}个体工商户[）]?',
            text
        ):
            candidates.append((m.start(), m.group()))

        # 模式3: 经营部/服务站等
        for m in re.finditer(
            r'[\u4e00-\u9fa5（）]{4,}(?:经营部|服务站|服务中心)',
            text
        ):
            candidates.append((m.start(), m.group()))

        if not candidates:
            return ""

        # 按文本位置排序
        candidates.sort(key=lambda x: x[0])

        # 过滤银行/金融机构
        companies = [name for _, name in candidates
                     if not any(kw in name for kw in bank_keywords)]

        if not companies:
            return ""

        if field == 'buyer_name':
            # 购买方：第一个非银行公司名
            return companies[0]

        elif field == 'seller_name':
            # 销售方：最后一个非银行公司名
            # 需要至少2个不同公司才区分买卖方
            if len(companies) >= 2:
                return companies[-1]
            # 只有一个公司时，它可能是销售方
            return companies[0] if companies else ""

        return ""

    @staticmethod
    def _extract_tax_amount(text: str, extraction_config: dict) -> str:
        """
        智能提取税额

        当税额正则误匹配为不含税金额时，尝试提取发票中
        第二个或第三个数字（通常排列为：金额 税率 税额）。
        """
        import re
        # 在发票数字行中查找：数字 百分比% 数字 的模式
        # 匹配类似 "248.66 1% 2.49" 的行
        m = re.search(r'(\d+\.\d{2})\s+\d+%\s+(\d+\.\d{2})', text)
        if m:
            return m.group(2)  # 税额是第三个数字

        # 备选：在 "¥金额 ¥税额" 行中找第二个数字
        m = re.search(r'¥[\d.]+\s+¥([\d.]+)', text)
        if m:
            return m.group(1)

        return ""

    @staticmethod
    def _extract_total_amount(text: str) -> str:
        """
        智能提取价税合计

        查找所有 ¥ 后的数字，返回最大值（价税合计通常是最大的）。
        """
        import re
        # 查找所有 ¥ 符号后的数字（包括有空格的情况）
        amounts = re.findall(r'¥\s*([\d.]+)', text)
        if not amounts:
            return ""

        # 转换为浮点数找最大值
        try:
            numeric = []
            for a in amounts:
                try:
                    numeric.append((float(a), a))
                except ValueError:
                    pass
            if numeric:
                # 返回最大的那个
                return max(numeric, key=lambda x: x[0])[1]
        except Exception:
            pass

        # 回退：找文本中最后一个 ¥ 后的数字
        last_yen = text.rfind('¥')
        if last_yen >= 0:
            after = text[last_yen:]
            m = re.search(r'¥\s*([\d.]+)', after)
            if m:
                return m.group(1)

        return ""

    @staticmethod
    def _try_regex(pattern: str, text: str, flags: int = 0) -> str:
        """尝试正则匹配，返回捕获组1或组0，失败返回空字符串"""
        import re
        try:
            match = re.search(pattern, text, flags)
            if match and match.groups():
                return match.group(1).strip()
            elif match:
                return match.group(0).strip()
        except re.error:
            pass
        return ""

    @staticmethod
    def _compare_results(ai_data: dict, parsed: dict) -> dict:
        """
        对比 AI 识别结果和规则解析结果
        
        Returns:
            {"match": bool, "diff": str}
        """
        import re as _re

        # 字符串字段：精确匹配
        str_fields = ['invoice_number', 'invoice_date', 'seller_name', 'buyer_name']
        # 金额字段：容差 0.02
        amount_fields = ['amount_without_tax', 'tax_amount', 'total_amount']

        diffs = []

        for field in str_fields:
            ai_val = str(ai_data.get(field, '')).strip()
            parsed_val = str(parsed.get(field, '')).strip()
            # 两者都非空且不相等时才报告差异
            if ai_val and parsed_val and ai_val != parsed_val:
                diffs.append(
                    f"  {field}: 预期「{ai_val}」, 实际提取「{parsed_val}」"
                )
            elif ai_val and not parsed_val:
                diffs.append(f"  {field}: 预期「{ai_val}」, 实际未提取到")

        for field in amount_fields:
            ai_val = float(ai_data.get(field, 0) or 0)
            parsed_raw = str(parsed.get(field, '')).strip()
            if parsed_raw:
                try:
                    cleaned = _re.sub(r'[¥￥$€\s,，]', '', parsed_raw)
                    parsed_val = float(cleaned)
                except ValueError:
                    parsed_val = 0.0
            else:
                parsed_val = 0.0

            if ai_val > 0 and abs(ai_val - parsed_val) > 0.02:
                diffs.append(
                    f"  {field}: 预期 {ai_val:.2f}, 实际提取 {parsed_val:.2f}"
                )

        return {
            "match": len(diffs) == 0,
            "diff": "\n".join(diffs) if diffs else ""
        }

    @staticmethod
    def _analyze_failure_reason(field: str, expected: str, actual: str) -> str:
        """
        分析字段提取失败的可能原因

        根据预期值和实际提取值之间的差异，给出失败原因提示，
        供 error_context 使用，帮助 AI 在重试时做出有针对性的修正。
        """
        actual_lower = actual.lower() if actual else ""
        expected_lower = expected.lower() if expected else ""

        # 银行/金融机构名称检测
        bank_keywords = ['银行', '支行', '分行', '信用社', '分理处', '营业部']
        if any(kw in actual for kw in bank_keywords):
            return (
                f"匹配到了银行/金融机构名称「{actual}」而非真正的{field}。"
                f"真正的{field}「{expected}」不含银行关键字。"
                f"请确保正则在匹配公司名时排除含银行/支行/分行/信用社的名称。"
            )

        # seller_name 特定分析
        if field == 'seller_name':
            if actual and actual in expected:
                return (
                    f"正则仅截取了{field}的一部分「{actual}」，"
                    f"完整名称应为「{expected}」。"
                    f"可能是正则中字符数下限过低，或匹配范围不够完整。"
                )
            if expected and expected in actual:
                return (
                    f"正则匹配到了多余内容「{actual}」，"
                    f"预期目标仅「{expected}」。"
                    f"请缩小正则的匹配范围，避免捕获到相邻无关文本。"
                )
            # 检查是否匹配到购买方名称（两者混淆）
            return (
                f"正则在错误位置匹配到了「{actual}」，"
                f"真正的{field}为「{expected}」。"
                f"提示：销售方名称通常在文本中间位置（信用代码附近），"
                f"而非末尾备注区。请换用基于信用代码定位的策略。"
            )

        # buyer_name 特定分析
        if field == 'buyer_name':
            if actual and actual in expected:
                return (
                    f"正则仅截取了{field}的一部分「{actual}」，"
                    f"完整名称应为「{expected}」。"
                )
            return (
                f"正则在错误位置匹配到了「{actual}」，"
                f"真正的{field}为「{expected}」。"
                f"提示：购买方名称通常是文本中第一个出现的公司全称。"
            )

        # 日期字段
        if field == 'invoice_date':
            return (
                f"日期格式不匹配。预期「{expected}」，实际提取「{actual}」。"
                f"请使用 \\d{{4}}年\\d{{1,2}}月\\d{{1,2}}日 模式匹配。"
            )

        # 金额字段
        if field in ('amount_without_tax', 'tax_amount', 'total_amount'):
            return (
                f"金额数值不匹配。预期 {expected}，实际提取 {actual}。"
                f"请检查是否匹配到了错误的数字（如税额与不含税金额混淆）。"
            )

        # 发票号码
        if field == 'invoice_number':
            return (
                f"发票号码不匹配。预期「{expected}」，实际提取「{actual}」。"
                f"请使用长数字模式 \\d{{8,20}} 匹配文本中最长的连续数字串。"
            )

        # 通用
        return (
            f"正则提取结果与预期不符。预期「{expected}」，实际提取「{actual}」。"
            f"请仔细检查发票原文，调整正则匹配策略。"
        )

    @staticmethod
    def _build_error_context(ai_data: dict, parsed: dict,
                              extraction_config: dict) -> str:
        """
        构建增强的 error_context，包含失败正则和失败原因分析

        相比旧的只返回差异信息，新版本包含：
        1. 每个失败字段的具体正则表达式
        2. 预期值 vs 实际提取值
        3. AI 分析的失败原因和改进建议
        """
        str_fields = ['invoice_number', 'invoice_date', 'seller_name', 'buyer_name']
        amount_fields = ['amount_without_tax', 'tax_amount', 'total_amount']

        failed_info_parts = []

        for field in str_fields:
            ai_val = str(ai_data.get(field, '')).strip()
            parsed_val = str(parsed.get(field, '')).strip()
            if not ai_val or not parsed_val or ai_val == parsed_val:
                continue

            # 获取该字段的正则
            pattern = extraction_config.get(field, '')
            if isinstance(pattern, dict):
                pattern = pattern.get('pattern', '')
            if not pattern:
                pattern = '(未生成正则)'

            # 分析失败原因
            reason = BatchLearnWorker._analyze_failure_reason(
                field, ai_val, parsed_val
            )

            info = (
                f"【{field}】\n"
                f"  失败正则: {pattern}\n"
                f"  预期值: 「{ai_val}」\n"
                f"  实际提取: 「{parsed_val}」\n"
                f"  失败原因: {reason}"
            )
            failed_info_parts.append(info)

        for field in amount_fields:
            ai_val = float(ai_data.get(field, 0) or 0)
            parsed_raw = str(parsed.get(field, '')).strip()
            if not parsed_raw or ai_val <= 0:
                continue
            try:
                import re as _re
                cleaned = _re.sub(r'[¥￥$€\s,，]', '', parsed_raw)
                parsed_val = float(cleaned)
            except ValueError:
                parsed_val = 0.0

            if abs(ai_val - parsed_val) <= 0.02:
                continue

            pattern = extraction_config.get(field, '')
            if isinstance(pattern, dict):
                pattern = pattern.get('pattern', '')
            if not pattern:
                pattern = '(未生成正则)'

            reason = BatchLearnWorker._analyze_failure_reason(
                field, str(ai_val), str(parsed_val)
            )

            info = (
                f"【{field}】\n"
                f"  失败正则: {pattern}\n"
                f"  预期值: {ai_val:.2f}\n"
                f"  实际提取: {parsed_val:.2f}\n"
                f"  失败原因: {reason}"
            )
            failed_info_parts.append(info)

        if not failed_info_parts:
            return "(无详细差异信息)"

        return "\n\n".join(failed_info_parts)


class AIPage(QWidget):
    """AI 智能识别页面"""

    invoice_imported = pyqtSignal()  # 通知外部刷新发票数据

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_paths: list[str] = []
        self._results: dict[str, dict] = {}  # file_path → result dict
        self._worker: BatchAIWorker | None = None
        self._learn_worker: BatchLearnWorker | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # === 标题栏 ===
        header = QHBoxLayout()
        title = QLabel("AI 智能识别")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # === 上部区域：文件选择 + AI 配置 ===
        top_split = QSplitter(Qt.Horizontal)

        # -- 文件选择区 --
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout(file_group)

        btn_row = QHBoxLayout()
        self._add_file_btn = QPushButton("添加文件")
        self._add_file_btn.setStyleSheet(self._btn_style("#1890ff"))
        self._add_file_btn.clicked.connect(self._on_add_files)
        btn_row.addWidget(self._add_file_btn)

        self._add_folder_btn = QPushButton("添加文件夹")
        self._add_folder_btn.setStyleSheet(self._btn_style("#1890ff"))
        self._add_folder_btn.clicked.connect(self._on_add_folder)
        btn_row.addWidget(self._add_folder_btn)

        self._clear_files_btn = QPushButton("清空")
        self._clear_files_btn.setStyleSheet(self._btn_style("#ff4d4f"))
        self._clear_files_btn.clicked.connect(self._on_clear_files)
        btn_row.addWidget(self._clear_files_btn)
        btn_row.addStretch()
        file_layout.addLayout(btn_row)

        self._file_list_widget = QLabel("未选择文件")
        self._file_list_widget.setStyleSheet("color: #999; padding: 5px;")
        self._file_list_widget.setWordWrap(True)
        file_layout.addWidget(self._file_list_widget)

        self._file_count_label = QLabel("")
        self._file_count_label.setStyleSheet("color: #666; font-size: 12px;")
        file_layout.addWidget(self._file_count_label)

        top_split.addWidget(file_group)

        # -- 学习过程展示区 --
        learn_log_group = QGroupBox("学习过程")
        learn_log_layout = QVBoxLayout(learn_log_group)
        learn_log_layout.setContentsMargins(5, 5, 5, 5)

        self._learn_log_view = QTextEdit()
        self._learn_log_view.setReadOnly(True)
        self._learn_log_view.setPlaceholderText("批量AI识别/学习的过程和结果将在此实时展示")
        self._learn_log_view.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                background-color: #fafafa;
                border: 1px solid #e8e8e8;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        learn_log_layout.addWidget(self._learn_log_view)

        top_split.addWidget(learn_log_group)
        top_split.setStretchFactor(0, 1)
        top_split.setStretchFactor(1, 2)
        layout.addWidget(top_split)

        # === 操作栏 ===
        action_row = QHBoxLayout()

        self._start_btn = QPushButton("🔍 开始批量识别")
        self._start_btn.setStyleSheet("""
            QPushButton { background-color: #722ed1; color: white; border: none;
                          padding: 10px 30px; border-radius: 4px;
                          font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #9254de; }
            QPushButton:disabled { background-color: #d9d9d9; }
        """)
        self._start_btn.clicked.connect(self._on_start_batch)
        action_row.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setStyleSheet(self._btn_style("#ff4d4f"))
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._cancel_btn.hide()
        action_row.addWidget(self._cancel_btn)

        action_row.addStretch()

        self._import_all_btn = QPushButton("全部导入数据库")
        self._import_all_btn.setStyleSheet(self._btn_style("#1890ff"))
        self._import_all_btn.setEnabled(False)
        self._import_all_btn.clicked.connect(self._on_import_all)
        action_row.addWidget(self._import_all_btn)

        self._learn_all_btn = QPushButton("批量 AI 学习")
        self._learn_all_btn.setStyleSheet(self._btn_style("#722ed1"))
        self._learn_all_btn.setEnabled(False)
        self._learn_all_btn.clicked.connect(self._on_batch_learn)
        action_row.addWidget(self._learn_all_btn)

        layout.addLayout(action_row)

        # === 进度栏 ===
        self._progress_widget = QWidget()
        prog_layout = QHBoxLayout(self._progress_widget)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumHeight(8)
        prog_layout.addWidget(self._progress_bar)
        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet("color: #1890ff; min-width: 200px;")
        prog_layout.addWidget(self._progress_label)
        self._progress_widget.hide()
        layout.addWidget(self._progress_widget)

        # === 结果表格 ===
        self._result_table = QTableWidget()
        self._result_table.setColumnCount(9)
        self._result_table.setHorizontalHeaderLabels([
            "文件名", "发票号码", "开票日期", "购买方", "销售方",
            "不含税", "税额", "价税合计", "操作"
        ])
        self._result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._result_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._result_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._result_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._result_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self._result_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self._result_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed)
        self._result_table.setColumnWidth(8, 160)
        self._result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.setAlternatingRowColors(True)
        self._result_table.setStyleSheet("""
            QTableWidget { gridline-color: #f0f0f0; }
            QTableWidget::item { padding: 4px; }
            QHeaderView::section {
                background-color: #fafafa; border: 1px solid #e8e8e8;
                padding: 6px; font-weight: bold;
            }
        """)
        layout.addWidget(self._result_table, 1)

        # === 状态栏 ===
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # 文件管理
    # ------------------------------------------------------------------

    def _on_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择发票文件", "",
            "发票文件 (*.xml *.pdf *.ofd);;所有文件 (*.*)"
        )
        if files:
            self._add_paths(files)

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            files = get_files_from_folder(folder)
            if files:
                self._add_paths(files)
            else:
                QMessageBox.information(self, "提示", "文件夹中没有找到支持的发票文件")

    def _add_paths(self, paths: list):
        for p in paths:
            if p not in self._file_paths and is_supported_file(p):
                self._file_paths.append(p)
        self._update_file_display()

    def _on_clear_files(self):
        self._file_paths.clear()
        self._results.clear()
        self._result_table.setRowCount(0)
        self._update_file_display()
        self._import_all_btn.setEnabled(False)
        self._learn_all_btn.setEnabled(False)

    def _update_file_display(self):
        count = len(self._file_paths)
        if count == 0:
            self._file_list_widget.setText("未选择文件")
            self._file_count_label.setText("")
        else:
            names = [Path(p).name for p in self._file_paths[:10]]
            text = "、".join(names)
            if count > 10:
                text += f" ... 等共 {count} 个文件"
            self._file_list_widget.setText(text)
            self._file_count_label.setText(f"共 {count} 个文件待识别")

    # ------------------------------------------------------------------
    # 学习过程日志
    # ------------------------------------------------------------------

    def _append_learn_log(self, msg: str, tag: str = "info"):
        """向学习过程展示区追加一条日志

        Args:
            msg: 日志文本
            tag: 标签 — 'info'(灰), 'success'(绿), 'warn'(橙), 'error'(红),
                  'step'(蓝), 'header'(紫)
        """
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")

        color_map = {
            'info': '#555',
            'success': '#52c41a',
            'warn': '#fa8c16',
            'error': '#ff4d4f',
            'step': '#1890ff',
            'header': '#722ed1',
        }
        color = color_map.get(tag, '#555')

        self._learn_log_view.append(
            f"<span style='color:#999;'>[{ts}]</span> "
            f"<span style='color:{color};'>{msg}</span>"
        )
        # 滚动到底部
        self._learn_log_view.moveCursor(
            self._learn_log_view.textCursor().End
        )

    def _clear_learn_log(self):
        """清空学习过程展示区"""
        self._learn_log_view.clear()

    # ------------------------------------------------------------------
    # 批量识别
    # ------------------------------------------------------------------

    def _on_start_batch(self):
        if not self._file_paths:
            QMessageBox.information(self, "提示", "请先添加发票文件")
            return

        # 清空旧结果
        self._results.clear()
        self._result_table.setRowCount(0)
        self._clear_learn_log()

        self._append_learn_log(
            f"🔍 开始批量识别 {len(self._file_paths)} 个文件", "header"
        )

        # 启动批量工作
        self._start_btn.setEnabled(False)
        self._cancel_btn.show()
        self._progress_widget.show()
        self._progress_bar.setMaximum(len(self._file_paths))
        self._progress_bar.setValue(0)
        self._import_all_btn.setEnabled(False)
        self._learn_all_btn.setEnabled(False)

        self._worker = BatchAIWorker(self._file_paths)
        self._worker.progress.connect(self._on_batch_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.all_done.connect(self._on_batch_done)
        self._worker.start()

        logger.info(f"[AI批量] 开始批量识别 {len(self._file_paths)} 个文件")

    def _on_cancel(self):
        if self._worker:
            self._worker.cancel()
            logger.info("[AI批量] 用户取消批量识别")
            self._append_learn_log("⏹ 批量识别已取消", "warn")
        if self._learn_worker:
            self._learn_worker.cancel()
            logger.info("[批量学习] 用户取消批量学习")
            self._append_learn_log("⏹ 批量学习已取消", "warn")

    def _on_batch_progress(self, current: int, total: int, filename: str):
        self._progress_bar.setValue(current)
        self._progress_label.setText(f"({current}/{total}) {filename}")

    def _on_file_done(self, file_path: str, result):
        """单个文件分析完成"""
        name = Path(file_path).name

        if isinstance(result, Exception):
            self._add_result_row(file_path, name, None, str(result))
            logger.warning(f"[AI批量] 失败: {name}, 错误: {result}")
            self._append_learn_log(
                f"✗ {name} — 识别失败: {result}", "error"
            )
        else:
            self._results[file_path] = result
            self._add_result_row(file_path, name, result, None)
            inv_no = result.get('invoice_number', '')
            total = result.get('total_amount', 0)
            logger.info(
                f"[AI批量] 成功: {name}, "
                f"发票号码={inv_no}, "
                f"价税合计={total}"
            )
            warn = result.get('validation_warning', '')
            if warn:
                self._append_learn_log(
                    f"⚠ {name} — 识别成功 (号码={inv_no}, 合计=¥{total:.2f}), "
                    f"金额校验警告: {warn}", "warn"
                )
            else:
                self._append_learn_log(
                    f"✓ {name} — 识别成功 (号码={inv_no}, 合计=¥{total:.2f})",
                    "success"
                )

    def _on_batch_done(self):
        """批量识别全部完成"""
        self._cleanup_worker()
        self._start_btn.setEnabled(True)
        self._cancel_btn.hide()
        self._progress_widget.hide()

        success_count = len(self._results)
        total = len(self._file_paths)
        self._status_label.setText(
            f"识别完成: {success_count}/{total} 成功"
        )
        if success_count > 0:
            self._import_all_btn.setEnabled(True)
            self._learn_all_btn.setEnabled(True)

        logger.info(f"[AI批量] 全部完成: {success_count}/{total} 成功")

        if success_count == total:
            self._append_learn_log(
                f"✅ 批量识别完成: 全部 {total} 个文件识别成功", "header"
            )
        else:
            self._append_learn_log(
                f"⚠ 批量识别完成: {success_count}/{total} 成功, {total - success_count} 失败",
                "header"
            )

    def _cleanup_worker(self):
        if self._worker is not None:
            self._worker.wait(5000)
            self._worker.deleteLater()
            self._worker = None

    def _cleanup_learn_worker(self):
        if self._learn_worker is not None:
            self._learn_worker.wait(5000)
            self._learn_worker.deleteLater()
            self._learn_worker = None

    # ------------------------------------------------------------------
    # 结果表格
    # ------------------------------------------------------------------

    def _add_result_row(self, file_path: str, name: str,
                        data: dict | None, error: str | None):
        row = self._result_table.rowCount()
        self._result_table.insertRow(row)

        # 文件名
        self._result_table.setItem(row, 0, QTableWidgetItem(name))

        if data:
            self._result_table.setItem(row, 1, QTableWidgetItem(
                str(data.get('invoice_number', ''))))
            self._result_table.setItem(row, 2, QTableWidgetItem(
                str(data.get('invoice_date', ''))))
            self._result_table.setItem(row, 3, QTableWidgetItem(
                str(data.get('buyer_name', ''))))
            self._result_table.setItem(row, 4, QTableWidgetItem(
                str(data.get('seller_name', ''))))
            self._result_table.setItem(row, 5, QTableWidgetItem(
                f"¥{data.get('amount_without_tax', 0):.2f}"))
            self._result_table.setItem(row, 6, QTableWidgetItem(
                f"¥{data.get('tax_amount', 0):.2f}"))
            self._result_table.setItem(row, 7, QTableWidgetItem(
                f"¥{data.get('total_amount', 0):.2f}"))

            # 警告标记
            warning = data.get('validation_warning', '')
            if warning:
                for col in (5, 6, 7):
                    item = self._result_table.item(row, col)
                    if item:
                        item.setForeground(QColor("#faad14"))
                        item.setToolTip(warning)
        else:
            # 失败行
            err_item = QTableWidgetItem(f"❌ {error or '未知错误'}")
            err_item.setForeground(QColor("#ff4d4f"))
            self._result_table.setItem(row, 1, err_item)
            for col in range(2, 8):
                self._result_table.setItem(row, col, QTableWidgetItem("—"))

        # 操作按钮
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(3, 2, 3, 2)
        btn_layout.setSpacing(4)

        if data:
            import_btn = QPushButton("导入")
            import_btn.setStyleSheet(self._btn_style("#1890ff"))
            import_btn.clicked.connect(
                lambda _, fp=file_path, d=data: self._on_import_single(fp, d))
            btn_layout.addWidget(import_btn)

            learn_btn = QPushButton("AI 学习")
            learn_btn.setStyleSheet(self._btn_style("#722ed1"))
            learn_btn.clicked.connect(
                lambda _, fp=file_path: self._on_learn_single(fp))
            btn_layout.addWidget(learn_btn)
        else:
            retry_btn = QPushButton("重试")
            retry_btn.setStyleSheet(self._btn_style("#fa8c16"))
            retry_btn.clicked.connect(
                lambda _, fp=file_path: self._on_retry_single(fp))
            btn_layout.addWidget(retry_btn)

        btn_layout.addStretch()
        self._result_table.setCellWidget(row, 8, btn_widget)

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------

    def _on_import_single(self, file_path: str, data: dict):
        """导入单个识别结果"""
        invoice = self._build_invoice(file_path, data)
        if not invoice:
            return

        if invoice_dao.exists_by_number(invoice.invoice_number):
            QMessageBox.warning(
                self, "重复",
                f"发票号码 {invoice.invoice_number} 已存在")
            return

        try:
            invoice_dao.insert(invoice)
            self.invoice_imported.emit()
            QMessageBox.information(self, "成功", f"发票 {invoice.invoice_number} 已导入")
            logger.info(f"[AI导入] 单张导入成功: {invoice.invoice_number}")
        except Exception as e:
            QMessageBox.warning(self, "导入失败", str(e))
            logger.error(f"[AI导入] 单张导入失败: {e}")

    def _on_import_all(self):
        """导入全部识别结果"""
        if not self._results:
            return

        success = 0
        skipped = 0
        failed = 0

        for file_path, data in self._results.items():
            invoice = self._build_invoice(file_path, data)
            if not invoice:
                failed += 1
                continue

            if invoice_dao.exists_by_number(invoice.invoice_number):
                skipped += 1
                continue

            try:
                invoice_dao.insert(invoice)
                success += 1
            except Exception:
                failed += 1

        self.invoice_imported.emit()
        msg = f"导入完成: 成功 {success}"
        if skipped:
            msg += f", 重复跳过 {skipped}"
        if failed:
            msg += f", 失败 {failed}"

        QMessageBox.information(self, "批量导入", msg)
        logger.info(f"[AI导入] 批量导入: 成功={success}, 跳过={skipped}, 失败={failed}")

    def _on_learn_single(self, file_path: str):
        """对单个文件进行 AI 学习"""
        from views.ai_learn_dialog import AILearnDialog
        dialog = AILearnDialog(file_path, self)
        dialog.invoice_imported.connect(self.invoice_imported)
        dialog.exec_()

    # ------------------------------------------------------------------
    # 批量 AI 学习
    # ------------------------------------------------------------------

    def _on_batch_learn(self):
        """批量 AI 学习所有识别成功的文件"""
        if not self._results:
            QMessageBox.information(self, "提示", "没有可学习的识别结果")
            return

        count = len(self._results)
        reply = QMessageBox.question(
            self, "确认批量学习",
            f"将对 {count} 个识别成功的文件进行 AI 学习，\n"
            f"为每个文件自动创建解析规则。\n\n"
            f"📌 规则名称：取「销售方名称」，无则取「发票号码」\n"
            f"⏱️  每文件需调用一次 AI，耗时较长\n\n"
            f"是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._clear_learn_log()
        self._append_learn_log(
            f"🤖 开始批量AI学习 {len(self._results)} 个文件", "header"
        )

        # 准备数据
        items = [(fp, data) for fp, data in self._results.items()]

        # 禁用按钮，显示进度
        self._start_btn.setEnabled(False)
        self._learn_all_btn.setEnabled(False)
        self._import_all_btn.setEnabled(False)
        self._cancel_btn.show()
        self._progress_widget.show()
        self._progress_bar.setMaximum(len(items))
        self._progress_bar.setValue(0)

        self._learn_worker = BatchLearnWorker(items)
        self._learn_worker.progress.connect(self._on_batch_progress)
        self._learn_worker.progress.connect(
            lambda c, t, f: self._append_learn_log(
                f"📄 ({c}/{t}) 开始学习: {f}", "step"
            )
        )
        self._learn_worker.learn_log.connect(self._append_learn_log)
        self._learn_worker.file_done.connect(self._on_learn_file_done)
        self._learn_worker.all_done.connect(self._on_batch_learn_done)
        self._learn_worker.start()

        logger.info(f"[批量学习] 开始批量学习 {len(items)} 个文件")

    def _on_learn_file_done(self, file_path: str, success: bool, message: str):
        """单个文件学习完成回调"""
        name = Path(file_path).name
        if success:
            logger.info(f"[批量学习] 完成: {name}, {message}")
            self._append_learn_log(f"✓ {name} — {message}", "success")
        else:
            logger.warning(f"[批量学习] 失败: {name}, {message}")
            self._append_learn_log(f"✗ {name} — {message}", "error")

    def _on_batch_learn_done(self):
        """批量学习全部完成"""
        self._cleanup_learn_worker()
        self._start_btn.setEnabled(True)
        self._learn_all_btn.setEnabled(True)
        self._import_all_btn.setEnabled(True)
        self._cancel_btn.hide()
        self._progress_widget.hide()

        self._append_learn_log("✅ 批量AI学习完成", "header")

        QMessageBox.information(
            self, "完成",
            "批量 AI 学习已完成。\n"
            "详情请查看下方「学习过程」面板或「规则管理」页面。"
        )

        logger.info("[批量学习] 全部完成")

    def _on_retry_single(self, file_path: str):
        """重试单个文件的 AI 识别"""
        name = Path(file_path).name

        # 移除旧行
        for row in range(self._result_table.rowCount()):
            item = self._result_table.item(row, 0)
            if item and item.text() == name:
                self._result_table.removeRow(row)
                break

        try:
            result = ai_service.analyze_invoice(file_path)
            self._results[file_path] = result
            self._add_result_row(file_path, name, result, None)
            self._import_all_btn.setEnabled(bool(self._results))
            self._learn_all_btn.setEnabled(bool(self._results))
        except Exception as e:
            self._add_result_row(file_path, name, None, str(e))

    def _build_invoice(self, file_path: str, data: dict) -> Invoice | None:
        """从 AI 结果构建 Invoice 对象"""
        inv_number = str(data.get('invoice_number', '')).strip()
        inv_date = str(data.get('invoice_date', '')).strip()

        if not inv_number:
            logger.warning(f"[AI导入] 发票号码为空: {file_path}")
            return None
        if not inv_date:
            logger.warning(f"[AI导入] 开票日期为空: {file_path}")
            return None

        invoice = Invoice(
            business_type=data.get('business_type', '其他'),
            invoice_type=data.get('invoice_type', '其他'),
            invoice_number=inv_number,
            invoice_date=inv_date,
            buyer_name=str(data.get('buyer_name', '')),
            seller_name=str(data.get('seller_name', '')),
            amount_without_tax=float(data.get('amount_without_tax', 0)),
            tax_amount=float(data.get('tax_amount', 0)),
            total_amount=float(data.get('total_amount', 0)),
            source_file_path=file_path,
            file_format=Path(file_path).suffix.lower().lstrip('.'),
            ai_learned=True,
        )
        invoice.set_import_time()
        return invoice

    # ------------------------------------------------------------------
    # 外部接口
    # ------------------------------------------------------------------

    def add_files_and_start(self, file_paths: list):
        """外部调用：添加文件并自动开始识别"""
        self._add_paths(file_paths)
        # 延迟启动（确保页面已显示）
        QTimer.singleShot(300, self._on_start_batch)

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _btn_style(color: str) -> str:
        return f"""
            QPushButton {{ background-color: {color}; color: white; border: none;
                          padding: 5px 12px; border-radius: 3px; font-size: 12px; }}
            QPushButton:hover {{ opacity: 0.85; }}
            QPushButton:disabled {{ background-color: #d9d9d9; }}
        """

    def showEvent(self, event):
        """页面显示时的处理"""
        super().showEvent(event)

    def closeEvent(self, event):
        self._cleanup_worker()
        self._cleanup_learn_worker()
        super().closeEvent(event)
