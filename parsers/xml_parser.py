"""XML 电子发票解析器"""

import xml.etree.ElementTree as ET
from pathlib import Path
from parsers.base_parser import BaseParser
from models.invoice import Invoice
from core.exceptions import ParseError
from core.constants import BusinessType, InvoiceType
from core.logger import logger
from utils.validators import normalize_date, parse_amount


class XMLParser(BaseParser):
    """XML 电子发票解析器"""
    
    # 常见的 XML 命名空间
    NAMESPACES = {
        'fp': 'http://www.chinatax.gov.cn/2013/05/cxfp',
        'n': 'http://www.chinatax.gov.cn/2013/05/cxfp',
        'cfx': 'http://www.chinatax.gov.cn/2013/05/cxfp',
        'ns': 'http://www.chinatax.gov.cn/2013/05/cxfp',
        'inv': 'http://www.chinatax.gov.cn/2013/05/cxfp',
    }
    
    def can_parse(self, file_path: str) -> bool:
        """判断是否为 XML 文件"""
        return Path(file_path).suffix.lower() == '.xml'
    
    def parse(self, file_path: str) -> Invoice:
        """解析 XML 发票"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 尝试多种 XML 结构
            invoice = self._parse_standard_xml(root)
            
            # 如果标准解析未提取到关键字段（发票号码 或 买方+卖方），尝试简单解析
            need_simple = (
                not invoice.invoice_number or
                (not invoice.buyer_name and not invoice.seller_name)
            )
            if need_simple:
                simple_invoice = self._parse_simple_xml(root)
                # 合并结果：simple_invoice 中的非空字段覆盖 invoice
                if not invoice.invoice_number and simple_invoice.invoice_number:
                    invoice.invoice_number = simple_invoice.invoice_number
                if not invoice.invoice_date and simple_invoice.invoice_date:
                    invoice.invoice_date = simple_invoice.invoice_date
                if not invoice.buyer_name and simple_invoice.buyer_name:
                    invoice.buyer_name = simple_invoice.buyer_name
                if not invoice.seller_name and simple_invoice.seller_name:
                    invoice.seller_name = simple_invoice.seller_name
                if invoice.amount_without_tax == 0 and simple_invoice.amount_without_tax > 0:
                    invoice.amount_without_tax = simple_invoice.amount_without_tax
                if invoice.tax_amount == 0 and simple_invoice.tax_amount > 0:
                    invoice.tax_amount = simple_invoice.tax_amount
                if invoice.total_amount == 0 and simple_invoice.total_amount > 0:
                    invoice.total_amount = simple_invoice.total_amount
            
            # 如果仍然缺失购买方/销售方，尝试文本降级提取
            if not invoice.buyer_name or not invoice.seller_name:
                text = self._extract_text_from_xml(root)
                if text:
                    from parsers.pdf_parser import PDFParser
                    temp_parser = PDFParser.__new__(PDFParser)
                    names = temp_parser._parse_generic_names(text)
                    if not invoice.buyer_name and names.get('buyer_name'):
                        invoice.buyer_name = names['buyer_name']
                    if not invoice.seller_name and names.get('seller_name'):
                        invoice.seller_name = names['seller_name']
            
            # 设置文件信息
            invoice.source_file_path = file_path
            invoice.file_format = 'xml'
            
            # 尝试推断业务类型
            if not invoice.business_type:
                invoice.business_type = self._infer_business_type(invoice)
            
            # 尝试推断发票类型
            if not invoice.invoice_type:
                invoice.invoice_type = InvoiceType.E_INVOICE.value
            
            logger.info(f"XML 发票解析成功: {invoice.invoice_number}")
            return invoice
            
        except ET.ParseError as e:
            raise ParseError(f"XML 文件格式错误: {e}")
        except Exception as e:
            logger.error(f"XML 解析失败: {file_path}, 错误: {e}")
            raise ParseError(f"XML 解析失败: {e}")
    
    def _parse_standard_xml(self, root: ET.Element) -> Invoice:
        """解析标准电子发票 XML"""
        invoice = Invoice()
        
        # 定义常见路径映射
        field_paths = {
            'invoice_number': [
                './/fp:InvoiceNo',
                './/InvoiceNo',
                './/fp:FaPiaoNo',
                './/FaPiaoNo',
                # 发票号码 (FPHM = 发票号码拼音缩写)
                './/fp:FPHM',
                './/FPHM',
                './/fp:InvoiceNumber',
                './/InvoiceNumber',
                './/invoiceNumber',
                # 注意：FPDM 是发票代码（同批次相同），不能作为发票号码！
            ],
            'invoice_date': [
                './/fp:InvoiceDate',
                './/InvoiceDate',
                './/fp:KPRQ',
                './/KPRQ',
                './/invoiceDate',
                './/InvoiceDate',
            ],
            'buyer_name': [
                './/fp:BuyerName',
                './/BuyerName',
                './/fp:GFMC',
                './/GFMC',
                './/buyerName',
                './/Buyer/Name',
                # 拼音变体
                './/fp:GMF_MC',
                './/GMF_MC',
                './/fp:GouFangMingCheng',
                './/GouFangMingCheng',
                # 中文变体（少数自定义 XML）
                './/购买方名称',
                './/购买方',
                './/购方名称',
            ],
            'seller_name': [
                './/fp:SellerName',
                './/SellerName',
                './/fp:XFMC',
                './/XFMC',
                './/sellerName',
                './/Seller/Name',
                # 拼音变体
                './/fp:XSF_MC',
                './/XSF_MC',
                './/fp:XiaoShouFangMingCheng',
                './/XiaoShouFangMingCheng',
                # 中文变体（少数自定义 XML）
                './/销售方名称',
                './/销售方',
                './/销方名称',
            ],
            'amount_without_tax': [
                './/fp:AmountWithoutTax',
                './/AmountWithoutTax',
                './/fp:HJJE',
                './/HJJE',
                './/amountWithoutTax',
            ],
            'tax_amount': [
                './/fp:TaxAmount',
                './/TaxAmount',
                './/fp:HJSE',
                './/HJSE',
                './/taxAmount',
            ],
            'total_amount': [
                './/fp:TotalAmount',
                './/TotalAmount',
                './/fp:JSHJ',
                './/JSHJ',
                './/totalAmount',
            ],
        }
        
        # 尝试带命名空间和不带命名空间
        for field, paths in field_paths.items():
            for path in paths:
                value = self._find_text(root, path)
                if value:
                    self._set_invoice_field(invoice, field, value)
                    break
        
        return invoice
    
    def _parse_simple_xml(self, root: ET.Element) -> Invoice:
        """解析简单结构的 XML"""
        invoice = Invoice()
        
        # 遍历所有元素，尝试匹配字段名
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            text = elem.text.strip() if elem.text else ''
            
            if not text:
                continue
            
            tag_lower = tag.lower()
            
            # 发票号码（注意：code/代码/FPDM 是发票代码，不能作为发票号码）
            if ('invoice' in tag_lower and ('no' in tag_lower or 'number' in tag_lower)):
                invoice.invoice_number = text
            elif '发票号码' in tag or 'fphm' in tag_lower:
                invoice.invoice_number = text
            # 开票日期
            elif ('invoice' in tag_lower and 'date' in tag_lower):
                invoice.invoice_date = normalize_date(text) or text
            elif '开票日期' in tag or 'kprq' in tag_lower:
                invoice.invoice_date = normalize_date(text) or text
            # 购买方名称 — 英文变体
            elif ('buyer' in tag_lower and 'name' in tag_lower):
                invoice.buyer_name = text
            elif ('purchaser' in tag_lower and 'name' in tag_lower):
                invoice.buyer_name = text
            # 购买方名称 — 拼音变体
            elif 'gfmc' in tag_lower or 'gmf_mc' in tag_lower or 'goufang' in tag_lower:
                invoice.buyer_name = text
            # 购买方名称 — 中文变体
            elif '购买方' in tag and '名称' in tag:
                invoice.buyer_name = text
            elif '购方' in tag and '名称' in tag:
                invoice.buyer_name = text
            # 销售方名称 — 英文变体
            elif ('seller' in tag_lower and 'name' in tag_lower):
                invoice.seller_name = text
            elif ('supplier' in tag_lower and 'name' in tag_lower):
                invoice.seller_name = text
            # 销售方名称 — 拼音变体
            elif 'xfmc' in tag_lower or 'xsf_mc' in tag_lower or 'xiaoshou' in tag_lower:
                invoice.seller_name = text
            # 销售方名称 — 中文变体
            elif '销售方' in tag and '名称' in tag:
                invoice.seller_name = text
            elif '销方' in tag and '名称' in tag:
                invoice.seller_name = text
            # 金额
            elif 'amount' in tag_lower and 'tax' not in tag_lower:
                invoice.amount_without_tax = parse_amount(text)
            elif 'tax' in tag_lower and 'amount' in tag_lower:
                invoice.tax_amount = parse_amount(text)
            elif 'total' in tag_lower:
                invoice.total_amount = parse_amount(text)
            elif '价税合计' in tag or 'jshj' in tag_lower:
                invoice.total_amount = parse_amount(text)
            elif '不含税金额' in tag or 'hjje' in tag_lower:
                invoice.amount_without_tax = parse_amount(text)
            elif '税额' in tag or 'hjse' in tag_lower:
                invoice.tax_amount = parse_amount(text)
        
        return invoice
    
    def _extract_text_from_xml(self, root) -> str:
        """从 XML 元素树中提取所有文本（用于降级文本匹配）"""
        texts = []
        for elem in root.iter():
            if elem.text:
                text = elem.text.strip()
                if text:
                    texts.append(text)
            if elem.tail:
                tail = elem.tail.strip()
                if tail:
                    texts.append(tail)
        return '\n'.join(texts)
    
    def _find_text(self, root: ET.Element, path: str) -> str:
        """查找元素文本，支持命名空间"""
        # 直接查找
        elem = root.find(path)
        if elem is not None and elem.text:
            return elem.text.strip()
        
        # 带命名空间查找
        for ns_prefix, ns_uri in self.NAMESPACES.items():
            try:
                elem = root.find(path, {ns_prefix: ns_uri})
                if elem is not None and elem.text:
                    return elem.text.strip()
            except Exception:
                continue
        
        return ''
    
    def _set_invoice_field(self, invoice: Invoice, field: str, value: str):
        """设置发票字段值"""
        if field == 'invoice_number':
            invoice.invoice_number = value
        elif field == 'invoice_date':
            invoice.invoice_date = normalize_date(value) or value
        elif field == 'buyer_name':
            invoice.buyer_name = value
        elif field == 'seller_name':
            invoice.seller_name = value
        elif field == 'amount_without_tax':
            invoice.amount_without_tax = parse_amount(value)
        elif field == 'tax_amount':
            invoice.tax_amount = parse_amount(value)
        elif field == 'total_amount':
            invoice.total_amount = parse_amount(value)
    
    def _infer_business_type(self, invoice: Invoice) -> str:
        """根据发票内容推断业务类型"""
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
