"""PDF 文本提取工具

提取流程：
1. 优先使用 pdfplumber 原始文本提取
2. 若文本为空，降级到 PyMuPDF (fitz) 提取
3. 若仍为空，降级到 OCR 通道（需安装 pytesseract + tesseract）
"""

from pathlib import Path
from core.logger import logger
from core.exceptions import ParseError


class TextExtractor:
    """PDF 文本提取器 — 多级降级提取"""

    @staticmethod
    def extract_text(file_path: str) -> str:
        """
        提取 PDF 全文

        多级降级策略：
        1. pdfplumber 原始提取
        2. PyMuPDF (fitz) 提取
        3. OCR (pytesseract) 提取
        """
        filename = Path(file_path).name
        
        # 策略 1: pdfplumber
        raw_text = TextExtractor._extract_pdfplumber(file_path)
        if raw_text and len(raw_text.strip()) > 20:
            logger.info(f"[PDF原始提取] {filename} ({len(raw_text)} 字符, pdfplumber)")
            return raw_text
        
        # 策略 2: PyMuPDF (fitz)
        fitz_text = TextExtractor._extract_fitz(file_path)
        if fitz_text and len(fitz_text.strip()) > 20:
            logger.info(f"[PDF原始提取] {filename} ({len(fitz_text)} 字符, fitz降级)")
            return fitz_text
        
        # 策略 3: OCR
        ocr_text = TextExtractor._extract_ocr(file_path)
        if ocr_text and len(ocr_text.strip()) > 20:
            logger.info(f"[PDF原始提取] {filename} ({len(ocr_text)} 字符, OCR降级)")
            return ocr_text
        
        # 全部失败，返回最原始的结果
        result = raw_text or fitz_text or ocr_text or ""
        logger.warning(f"[PDF原始提取] {filename} 文本提取不足 ({len(result)} 字符)")
        logger.info(f"[PDF原始提取] {filename} ({len(result)} 字符)\n{result}")
        return result

    @staticmethod
    def _extract_pdfplumber(file_path: str) -> str:
        """pdfplumber 提取"""
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                parts = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        parts.append(text)
                return '\n'.join(parts)
        except ImportError:
            logger.debug("pdfplumber 未安装")
            return ""
        except Exception as e:
            logger.debug(f"pdfplumber 提取失败: {e}")
            return ""

    @staticmethod
    def _extract_fitz(file_path: str) -> str:
        """PyMuPDF (fitz) 提取"""
        try:
            import fitz
            doc = fitz.open(file_path)
            parts = []
            for page in doc:
                text = page.get_text()
                if text:
                    parts.append(text)
            doc.close()
            return '\n'.join(parts)
        except ImportError:
            logger.debug("PyMuPDF 未安装")
            return ""
        except Exception as e:
            logger.debug(f"fitz 提取失败: {e}")
            return ""

    @staticmethod
    def _extract_ocr(file_path: str) -> str:
        """OCR 提取（扫描件降级）"""
        try:
            import pytesseract
            from PIL import Image
            import fitz
            
            logger.info(f"[OCR降级] 开始 OCR 识别: {Path(file_path).name}")
            doc = fitz.open(file_path)
            ocr_parts = []
            
            for page_num, page in enumerate(doc):
                # 渲染为图片 (300 DPI)
                mat = fitz.Matrix(300/72, 300/72)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # OCR 识别（中文+英文）
                text = pytesseract.image_to_string(img, lang='chi_sim+eng')
                if text and text.strip():
                    ocr_parts.append(text.strip())
            
            doc.close()
            result = '\n'.join(ocr_parts)
            if result:
                logger.info(f"[OCR降级] 成功提取 {len(result)} 字符")
            return result
            
        except ImportError:
            logger.debug("pytesseract/PIL 未安装，OCR 不可用")
            return ""
        except Exception as e:
            logger.warning(f"OCR 提取失败: {e}")
            return ""

    @staticmethod
    def extract_text_with_positions(file_path: str) -> list[dict]:
        """
        提取带位置信息的文本块

        Args:
            file_path: PDF 文件路径

        Returns:
            list[dict]: 文本块列表，每项包含 text, x0, y0, x1, y1
        """
        try:
            import pdfplumber

            text_blocks = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    words = page.extract_words()
                    for word in words:
                        text_blocks.append({
                            'text': word['text'],
                            'x0': word['x0'],
                            'y0': word['top'],
                            'x1': word['x1'],
                            'y1': word['bottom'],
                            'page': page.page_number
                        })

            logger.debug(f"提取 {len(text_blocks)} 个文本块")
            return text_blocks

        except Exception as e:
            logger.error(f"带位置文本提取失败: {e}")
            return []
