"""PDF 发票规则解析器 — 纯正则提取

使用 pdfplumber 原始文本输出，通过正则表达式提取 7 项核心字段：
  发票号码、开票日期、购买方、销售方、合计金额、合计税额、价税合计
"""

import re
from pathlib import Path
from parsers.base_parser import BaseParser
from parsers.text_extractor import TextExtractor
from models.invoice import Invoice
from core.exceptions import ParseError
from core.constants import BusinessType, InvoiceType
from core.logger import logger
from utils.validators import normalize_date, parse_amount

# ── 通用正则：用于无规则时的降级提取 ────────────────────────────────
_GENERIC_PATTERNS = {
    'invoice_number': [
        r'发票号码[：:]\s*(\d+)',
        r'No[.]?\s*[:.]\s*(\d{8,20})',
        r'发票号码\s+(\d+)',
    ],
    'invoice_date': [
        r'开票日期[：:]\s*([\d]{4}年[\d]{1,2}月[\d]{1,2}日)',
        r'开票日期[：:]\s*([\d]{4}-[\d]{1,2}-[\d]{1,2})',
        r'(\d{4}年\d{1,2}月\d{1,2}日)',
    ],
    'buyer_name': [
        # 标准格式：购买方 名称：xxx（停于"统一"或行尾，避免捕获信用代码）
        r'购\s*买\s*方[\s\S]*?名\s*称[：:]\s*([^\n\r]+?)(?:\s*统一|$)',
        # 紧凑格式：购买方名称：xxx（单行）
        r'购买方名称[：:]\s*([^\n\r]+?)(?:\s*统一|$)',
        # 多行列拆分：购 名称：xxx（停于 销 或行尾，避免吞并卖家名）
        r'购\s*名\s*称[：:]\s*([^\n\r]+?)(?:\s*销|\s*$)',
    ],
    'seller_name': [
        # 标准格式：销售方 名称：xxx（停于"统一"或行尾）
        r'销\s*售\s*方[\s\S]*?名\s*称[：:]\s*([^\n\r]+?)(?:\s*统一|$)',
        # 紧凑格式：销售方名称：xxx（单行）
        r'销售方名称[：:]\s*([^\n\r]+?)(?:\s*统一|$)',
        # 多行列拆分：销 名称：xxx
        r'销\s*名\s*称[：:]\s*([^\n\r]+)',
    ],
    'amount_without_tax': [
        r'合\s*计[\s\S]*?￥?([\d,]+\.[\d]{2})',
        r'不含税金额[\s\S]*?￥?([\d,]+\.[\d]{2})',
        # 铁路客票/简单发票：独立的 ¥ 金额
        r'[¥￥]([\d.]+)',
    ],
    'tax_amount': [
        # 合计行第二个 ¥ 金额（优先级最高，避免匹配表头）
        r'合\s*计\s*¥[\d.]+\s*¥([\d.]+)',
        # 税额标签后金额
        r'税\s*额[：:]*\s*¥?([\d.]+\.[\d]{2})',
        # 降级：税额附近 ¥ 金额
        r'税\s*额[\s\S]*?¥([\d.]+)',
    ],
    'total_amount': [
        # 价税合计（小写）¥xxx
        r'价税合计[\s\S]*?（小写）\s*¥?\s*([\d.]+\.[\d]{2})',
        # 价税合计后 ¥ 金额
        r'价税合计[\s\S]*?¥([\d.]+\.[\d]{2})',
        # 纯（小写）¥xxx
        r'（小写）\s*¥?\s*([\d.]+\.[\d]{2})',
        # 原有格式
        r'价税合计[\s\S]*?￥?([\d,]+\.[\d]{2})',
        # 铁路客票/简单发票：独立的 ¥ 金额
        r'[¥￥]([\d.]+)',
    ],
}


class PDFParser(BaseParser):
    """PDF 发票解析器 — 纯正则提取"""

    def __init__(self, rule_service=None):
        self.rule_service = rule_service

    def can_parse(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() == '.pdf'

    def parse(self, file_path: str) -> Invoice:
        """解析 PDF 发票"""
        try:
            text = TextExtractor.extract_text(file_path)

            if not text.strip():
                raise ParseError("PDF 文件无法提取文本，可能是扫描件")

            # 尝试使用规则解析
            invoice = self._parse_with_rules(text, file_path)

            if not invoice:
                invoice = self._parse_generic(text)

            invoice.source_file_path = file_path
            invoice.file_format = 'pdf'

            if not invoice.business_type:
                invoice.business_type = self._infer_business_type(text, invoice)
            if not invoice.invoice_type:
                invoice.invoice_type = self._infer_invoice_type(text)

            logger.info(f"PDF 发票解析成功: {invoice.invoice_number}")
            return invoice

        except Exception as e:
            logger.error(f"PDF 解析失败: {file_path}, 错误: {e}")
            if isinstance(e, ParseError):
                raise
            raise ParseError(f"PDF 解析失败: {e}")

    # ── 规则提取 ──────────────────────────────────────────────────

    def _parse_with_rules(self, text: str, file_path: str) -> Invoice:
        """使用规则的正则表达式逐字段提取"""
        if not self.rule_service:
            return None

        try:
            rule = self.rule_service.match_rule(text, 'pdf')
            if not rule:
                return None

            logger.debug(f"[PDF解析] 匹配规则: {rule.rule_name} (ID={rule.id})")

            invoice = Invoice()
            config = rule.extraction_config

            for field, pattern in config.items():
                if not pattern:
                    continue
                # 兼容旧格式：如果是 dict，取出 pattern 字段
                if isinstance(pattern, dict):
                    pattern = pattern.get('pattern', '')
                if not pattern:
                    continue

                value = self._try_match(pattern, text)
                if value:
                    self._set_field_value(invoice, field, value)
                else:
                    logger.debug(f"[PDF解析] 字段 {field}: 未匹配 (pattern={pattern[:60]}...)")

            # 降级补全：规则未提取到的字段用通用正则补
            if not invoice.buyer_name or not invoice.seller_name:
                generic = self._parse_generic_names(text)
                if not invoice.buyer_name:
                    invoice.buyer_name = generic.get('buyer_name', '')
                if not invoice.seller_name:
                    invoice.seller_name = generic.get('seller_name', '')

            # 补充：seller 为空但 buyer 有值时，用排除法查找非买方公司名
            # 注意：铁路客票（builtin_111）没有销售方，不应强填
            if (not invoice.seller_name and invoice.buyer_name
                    and rule.id != 'builtin_111'):
                fallback_seller = self._extract_seller_by_exclusion(
                    text, invoice.buyer_name
                )
                if fallback_seller:
                    logger.debug(
                        f"[PDF解析] seller为空, 排除法补全为: {fallback_seller}"
                    )
                    invoice.seller_name = fallback_seller

            # 终极兜底：标签全部缺失时用公司名模式按位置分配
            if not invoice.buyer_name and not invoice.seller_name:
                companies = self._extract_all_companies(text)
                if len(companies) >= 2:
                    invoice.buyer_name = companies[0]
                    invoice.seller_name = companies[-1]
                    logger.debug(
                        f"[PDF解析] 标签缺失兜底: buyer={companies[0]}, seller={companies[-1]}"
                    )
                elif len(companies) == 1:
                    if not invoice.buyer_name:
                        invoice.buyer_name = companies[0]
                    elif not invoice.seller_name:
                        invoice.seller_name = companies[0]

            # 纠错：AI-learned规则的seller_name正则可能误匹配到buyer_name
            # 根因：seller_name正则用 \d{18} 定位信用代码，但买方代码常在卖方前
            if (invoice.seller_name
                    and invoice.buyer_name
                    and invoice.seller_name == invoice.buyer_name
                    and rule.id.startswith('ai_learned_')):
                # 策略1: 通用标签定位正则
                generic_names = self._parse_generic_names(text)
                if (generic_names.get('seller_name')
                        and generic_names['seller_name'] != invoice.buyer_name):
                    logger.debug(
                        f"[PDF解析] seller_name==buyer_name({invoice.seller_name}), "
                        f"降级修正为: {generic_names['seller_name']}"
                    )
                    invoice.seller_name = generic_names['seller_name']
                else:
                    # 策略2: 查找所有公司名，取非buyer的作为seller
                    fallback_seller = self._extract_seller_by_exclusion(
                        text, invoice.buyer_name
                    )
                    if fallback_seller:
                        logger.debug(
                            f"[PDF解析] seller_name==buyer_name, "
                            f"排除法修正为: {fallback_seller}"
                        )
                        invoice.seller_name = fallback_seller

            if (invoice.amount_without_tax == 0 and invoice.tax_amount == 0
                    and invoice.total_amount == 0):
                generic = self._parse_generic(text)
                invoice.amount_without_tax = generic.amount_without_tax
                invoice.tax_amount = generic.tax_amount
                invoice.total_amount = generic.total_amount
                if not invoice.invoice_number and generic.invoice_number:
                    invoice.invoice_number = generic.invoice_number
                if not invoice.invoice_date and generic.invoice_date:
                    invoice.invoice_date = generic.invoice_date

            # 简单金额推导
            if invoice.total_amount == 0 and invoice.amount_without_tax > 0:
                invoice.total_amount = invoice.amount_without_tax + invoice.tax_amount
            if invoice.amount_without_tax == 0 and invoice.total_amount > 0:
                invoice.amount_without_tax = invoice.total_amount - invoice.tax_amount

            invoice.rule_id = rule.id
            return invoice

        except Exception as e:
            logger.debug(f"规则解析失败: {e}")
            return None

    # ── 通用降级提取 ──────────────────────────────────────────────

    def _parse_generic(self, text: str) -> Invoice:
        """通用正则提取（无规则时的降级方案）"""
        invoice = Invoice()

        for field, patterns in _GENERIC_PATTERNS.items():
            for pattern in patterns:
                value = self._try_match(pattern, text)
                if value:
                    self._set_field_value(invoice, field, value)
                    break

        # 终极兜底：标签完全缺失时用公司名模式按位置分配
        if not invoice.buyer_name and not invoice.seller_name:
            companies = self._extract_all_companies(text)
            if len(companies) >= 2:
                invoice.buyer_name = companies[0]
                invoice.seller_name = companies[-1]
            elif len(companies) == 1:
                invoice.buyer_name = companies[0]

        # 金额推导
        if invoice.total_amount == 0 and invoice.amount_without_tax > 0:
            invoice.total_amount = invoice.amount_without_tax + invoice.tax_amount
        if invoice.amount_without_tax == 0 and invoice.total_amount > 0:
            invoice.amount_without_tax = invoice.total_amount - invoice.tax_amount

        return invoice

    def _parse_generic_names(self, text: str) -> dict:
        """仅提取购买方和销售方名称（供规则降级补全使用）"""
        result = {}
        for field in ('buyer_name', 'seller_name'):
            for pattern in _GENERIC_PATTERNS.get(field, []):
                value = self._try_match(pattern, text)
                if value and self._is_valid_name(value):
                    result[field] = value.strip()
                    break
        return result

    @staticmethod
    def _extract_seller_by_exclusion(text: str, buyer_name: str) -> str:
        """
        策略2回退：在文本中查找所有公司名，排除buyer后返回最可能的seller

        用于 AI-learned 规则的 seller_name 正则误匹配到 buyer 时的兜底修复。
        """
        # 公司名称模式（覆盖常见后缀）
        company_pattern = (
            r'[\u4e00-\u9fa5（）()]{4,}'
            r'(?:有限(?:责任)?公司|股份有限公司|有限责任公司'
            r'|个体工商户[）)]?'
            r'|合伙企业|经营部|服务部|分公司'
            r'|(?:酒店|宾馆|餐饮|餐厅|烧烤店|饭店|旅馆|客栈)'
            r')'
        )
        candidates = []
        for m in re.finditer(company_pattern, text):
            name = m.group().strip()
            # 排除买方名和银行/金融机构
            if name and name != buyer_name:
                bank_kw = ['银行', '支行', '分行', '信用社', '信用合作']
                if not any(kw in name for kw in bank_kw):
                    if name not in candidates:
                        candidates.append(name)
        # 优先返回最后一个（销售方通常在文本后面）
        if candidates:
            return candidates[-1]
        return ''

    @staticmethod
    def _extract_all_companies(text: str) -> list:
        """
        终极兜底：从文本中提取所有公司名称（不依赖任何标签）

        按文本出现顺序返回，排除银行/金融机构。
        用于标签完全缺失时按位置分配买方/卖方。
        """
        company_pattern = (
            r'[\u4e00-\u9fa5（）()]{4,}'
            r'(?:有限(?:责任)?公司|股份有限公司|有限责任公司'
            r'|个体工商户[）)]?'
            r'|合伙企业|经营部|服务部|分公司'
            r'|(?:酒店|宾馆|餐饮|餐厅|烧烤店|饭店|旅馆|客栈)'
            r')'
        )
        candidates = []
        for m in re.finditer(company_pattern, text):
            name = m.group().strip()
            if name:
                bank_kw = ['银行', '支行', '分行', '信用社', '信用合作']
                if not any(kw in name for kw in bank_kw):
                    if name not in candidates:
                        candidates.append(name)
        return candidates

    # ── 正则匹配辅助 ──────────────────────────────────────────────

    @staticmethod
    def _try_match(pattern: str, text: str) -> str:
        """
        尝试正则匹配，返回 group(1) 或 group(0)，失败返回 ''

        多组日期模式特殊处理：
          当 pattern 包含多个捕获组且第一组为4位数字（年）时，
          返回完整匹配（group 0），以便调用方通过 normalize_date 提取完整日期。
          避免仅返回 group(1)="2026" 而丢失月、日信息。
        """
        try:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                groups = match.groups()
                if groups:
                    # 检测日期多组模式：第1组是4位数字（年），第2组也是数字（月/日）
                    if (len(groups) >= 2
                            and groups[0] and re.match(r'^\d{4}$', groups[0])
                            and groups[1] and re.match(r'^\d{1,2}$', groups[1])):
                        # 返回完整匹配，含原始分隔符（如"开票日期:2026年04月02日"）
                        return match.group(0).strip()
                    return groups[0].strip()
                return match.group(0).strip()
        except re.error:
            pass
        return ''

    def _set_field_value(self, invoice: Invoice, field: str, value: str):
        """设置发票字段值（类型转换）"""
        if field in ('amount_without_tax', 'tax_amount', 'total_amount'):
            setattr(invoice, field, parse_amount(value))
        elif field == 'invoice_date':
            invoice.invoice_date = normalize_date(value) or value
        else:
            setattr(invoice, field, value.strip())

    @staticmethod
    def _is_valid_name(name: str) -> bool:
        """检查名称是否有效（非纯数字/标点，至少2字符）"""
        if not name or len(name) < 2:
            return False
        if re.match(r'^[\d\s,.，。、·•\-－_（）()\\/]+$', name):
            return False
        return True

    # ── 类型推断 ──────────────────────────────────────────────────

    def _infer_business_type(self, text: str, invoice: Invoice) -> str:
        text_lower = f"{text} {invoice.seller_name}".lower()
        keywords_map = {
            BusinessType.RAILWAY.value: ['铁路', '12306', '火车票', '电子客票', '铁路电子'],
            BusinessType.FLIGHT.value: ['航空', '机票', '飞机', '航班'],
            BusinessType.TAXI.value: ['出租车', '打车', '滴滴', '网约车', 'didi', '客运'],
            BusinessType.CATERING.value: ['餐饮', '餐厅', '饭店', '美食', '食品'],
            BusinessType.HOTEL.value: ['酒店', '宾馆', '住宿', '旅馆', '客房'],
            BusinessType.OFFICE.value: ['办公', '文具', '办公用品', '耗材'],
            BusinessType.TELECOM.value: ['电信', '移动', '联通', '通讯', '话费'],
            BusinessType.GAS.value: ['加油', '石油', '石化', '加油站'],
            BusinessType.PARKING.value: ['停车', '停车场'],
            BusinessType.TOLL.value: ['过路费', '通行费', '高速'],
        }
        for biz_type, keywords in keywords_map.items():
            for kw in keywords:
                if kw in text_lower:
                    return biz_type
        return BusinessType.OTHER.value

    def _infer_invoice_type(self, text: str) -> str:
        if '增值税电子普通发票' in text or '电子发票' in text:
            return InvoiceType.E_INVOICE.value
        elif '增值税专用发票' in text:
            return InvoiceType.VAT_SPECIAL.value
        elif '增值税普通发票' in text:
            return InvoiceType.VAT_NORMAL.value
        elif '机打发票' in text:
            return InvoiceType.MACHINE_PRINT.value
        elif '定额发票' in text:
            return InvoiceType.FIXED_AMOUNT.value
        return InvoiceType.OTHER.value
