"""OFD 格式解析器 — 完整实现"""

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from parsers.base_parser import BaseParser
from models.invoice import Invoice
from core.exceptions import ParseError
from core.logger import logger


class OFDParser(BaseParser):
    """OFD 格式发票解析器"""
    
    # OFD 包内常见发票 XML 候选路径（按优先级排序）
    _CANDIDATE_PATHS = [
        'Doc_0/Content.xml',
        'Doc_0/Pages/Page_0/Content.xml',
        'Doc_0/Pages/Page_0/Page.xml',
        'Doc_0/Pages/Page_0/Contents.xml',
        'Doc_0/CustomTags/CustomTag.xml',
        'Doc_0/PublicRes.xml',
        'Doc_0/DocumentRes.xml',
        'Doc_0/Document.xml',
        'OFD.xml',
    ]
    
    def can_parse(self, file_path: str) -> bool:
        """判断是否为 OFD 文件"""
        return Path(file_path).suffix.lower() == '.ofd'
    
    def parse(self, file_path: str) -> Invoice:
        """
        解析 OFD 发票
        
        策略：
        1. 在 ZIP 内查找候选 XML 文件 → 委托给 XMLParser 解析
        2. 提取全部文本 → 使用 PDFParser 正则降级解析
        3. 均失败 → 抛出 ParseError，引导用户使用 AI 学习
        """
        logger.info(f"开始解析 OFD 文件: {file_path}")
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                names = zf.namelist()
                
                # 策略1: 查找并解析候选发票 XML
                candidate_files = self._find_invoice_xml(zf, names)
                
                for xml_name in candidate_files:
                    try:
                        content = zf.read(xml_name)
                        root = ET.fromstring(content)
                        invoice = self._parse_ofd_xml(root)
                        if invoice.invoice_number:
                            invoice.source_file_path = file_path
                            invoice.file_format = 'ofd'
                            if not invoice.business_type:
                                invoice.business_type = self._infer_business_type(invoice)
                            logger.info(
                                f"OFD 策略1 成功 [{xml_name}]: "
                                f"发票号码={invoice.invoice_number}"
                            )
                            return invoice
                    except ET.ParseError:
                        logger.debug(f"XML 解析失败，跳过: {xml_name}")
                        continue
                    except Exception as e:
                        logger.debug(f"解析 {xml_name} 异常: {e}")
                        continue
                
                # 策略2: 提取全部文本 → 正则降级
                all_text = self._extract_all_text_from_ofd(zf, names)
                if all_text.strip():
                    invoice = self._parse_with_regex_fallback(all_text, file_path)
                    if invoice.invoice_number:
                        invoice.source_file_path = file_path
                        invoice.file_format = 'ofd'
                        if not invoice.business_type:
                            invoice.business_type = self._infer_business_type(invoice)
                        logger.info(
                            f"OFD 策略2 成功: 发票号码={invoice.invoice_number}"
                        )
                        return invoice
                
                raise ParseError(
                    f"OFD 文件无法自动识别发票数据，请使用 AI 学习功能。\n"
                    f"文件: {Path(file_path).name}\n"
                    f"已扫描 {len(names)} 个文件，{len(candidate_files)} 个 XML"
                )
                
        except zipfile.BadZipFile:
            raise ParseError("无效的 OFD 文件（ZIP 格式损坏）")
        except Exception as e:
            logger.error(f"OFD 解析失败: {file_path}, 错误: {e}")
            if isinstance(e, ParseError):
                raise
            raise ParseError(f"OFD 解析失败: {e}")
    
    def _find_invoice_xml(self, zf: zipfile.ZipFile, names: list) -> list:
        """
        按优先级排序找到可能包含发票数据的 XML 文件
        
        优先级：
        1. 预定义候选路径
        2. 文件名含 "Content" 的 XML
        3. 包含"发票"关键字的 XML
        4. 所有 .xml 文件
        """
        result = []
        seen = set()
        
        # 优先级1: 预定义候选路径
        for path in self._CANDIDATE_PATHS:
            if path in names and path not in seen:
                result.append(path)
                seen.add(path)
            # 大小写变体
            lower_map = {n.lower(): n for n in names}
            if path.lower() in lower_map:
                actual = lower_map[path.lower()]
                if actual not in seen:
                    result.append(actual)
                    seen.add(actual)
        
        # 优先级2: 文件名含 "content" 的 XML
        for name in names:
            if name.lower().endswith('.xml') and 'content' in name.lower():
                if name not in seen:
                    result.append(name)
                    seen.add(name)
        
        # 优先级3: 包含"发票"关键字的 XML
        for name in names:
            if name.lower().endswith('.xml') and name not in seen:
                try:
                    content = zf.read(name)
                    text = content.decode('utf-8', errors='replace')[:2000]
                    if '发票' in text or 'invoice' in text.lower():
                        result.append(name)
                        seen.add(name)
                except Exception:
                    pass
        
        # 优先级4: 所有剩余 XML
        for name in names:
            if name.lower().endswith('.xml') and name not in seen:
                result.append(name)
                seen.add(name)
        
        return result
    
    def _parse_ofd_xml(self, root: ET.Element) -> Invoice:
        """
        解析 OFD 内部的 XML，复用 XMLParser 的逻辑
        """
        from parsers.xml_parser import XMLParser
        
        parser = XMLParser()
        
        # 先尝试标准解析
        invoice = parser._parse_standard_xml(root)
        
        # 如果标准解析未获取到关键字段，尝试简单解析
        if not invoice.invoice_number or (not invoice.buyer_name and not invoice.seller_name):
            simple = parser._parse_simple_xml(root)
            if not invoice.invoice_number and simple.invoice_number:
                invoice.invoice_number = simple.invoice_number
            if not invoice.invoice_date and simple.invoice_date:
                invoice.invoice_date = simple.invoice_date
            if not invoice.buyer_name and simple.buyer_name:
                invoice.buyer_name = simple.buyer_name
            if not invoice.seller_name and simple.seller_name:
                invoice.seller_name = simple.seller_name
            if invoice.amount_without_tax == 0 and simple.amount_without_tax > 0:
                invoice.amount_without_tax = simple.amount_without_tax
            if invoice.tax_amount == 0 and simple.tax_amount > 0:
                invoice.tax_amount = simple.tax_amount
            if invoice.total_amount == 0 and simple.total_amount > 0:
                invoice.total_amount = simple.total_amount
        
        return invoice
    
    def _extract_all_text_from_ofd(self, zf: zipfile.ZipFile, names: list) -> str:
        """从 OFD 所有 XML 中提取纯文本"""
        texts = []
        for name in names:
            if not name.lower().endswith('.xml'):
                continue
            try:
                content = zf.read(name)
                root = ET.fromstring(content)
                for elem in root.iter():
                    if elem.text:
                        t = elem.text.strip()
                        if t:
                            texts.append(t)
                    if elem.tail:
                        t = elem.tail.strip()
                        if t:
                            texts.append(t)
            except ET.ParseError:
                # 尝试直接解码
                try:
                    raw = zf.read(name).decode('utf-8', errors='replace')
                    # 简单提取标签间文本
                    import re
                    for match in re.finditer(r'>([^<]+)<', raw):
                        t = match.group(1).strip()
                        if t and len(t) > 1:
                            texts.append(t)
                except Exception:
                    continue
            except Exception:
                continue
        return '\n'.join(texts)
    
    def _parse_with_regex_fallback(self, text: str, file_path: str) -> Invoice:
        """使用 PDFParser 的通用正则解析作为降级"""
        from parsers.pdf_parser import PDFParser
        
        parser = PDFParser.__new__(PDFParser)
        return parser._parse_generic(text, file_path)
    
    def _infer_business_type(self, invoice: Invoice) -> str:
        """根据发票内容推断业务类型"""
        from core.constants import BusinessType
        
        text = f"{invoice.seller_name} {invoice.buyer_name}".lower()
        
        keywords_map = {
            BusinessType.RAILWAY.value: ['铁路', '12306', '火车票'],
            BusinessType.FLIGHT.value: ['航空', '机票', '飞机'],
            BusinessType.TAXI.value: ['出租车', '打车', '滴滴', '网约车'],
            BusinessType.CATERING.value: ['餐饮', '餐厅', '饭店', '美食'],
            BusinessType.HOTEL.value: ['酒店', '宾馆', '住宿', '旅馆'],
            BusinessType.OFFICE.value: ['办公', '文具', '办公用品'],
            BusinessType.TELECOM.value: ['电信', '移动', '联通', '通讯', '话费'],
            BusinessType.GAS.value: ['加油', '石油', '石化', '加油站'],
            BusinessType.PARKING.value: ['停车', '停车场'],
            BusinessType.TOLL.value: ['过路费', '通行费', '高速'],
        }
        
        for biz_type, keywords in keywords_map.items():
            for kw in keywords:
                if kw in text:
                    return biz_type
        
        return BusinessType.OTHER.value
