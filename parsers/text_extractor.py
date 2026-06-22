"""PDF 文本提取工具

统一使用 pdfplumber 原始 page.extract_text() 输出，
不做列拆分或额外加工，保持文本原始格式供正则匹配。
"""

from pathlib import Path
from core.logger import logger
from core.exceptions import ParseError


class TextExtractor:
    """PDF 文本提取器 — 仅输出 pdfplumber 原始文本"""

    @staticmethod
    def extract_text(file_path: str) -> str:
        """
        提取 PDF 全文

        直接使用 pdfplumber 的 page.extract_text() 原始输出，
        不做任何列拆分、位置调整等加工处理。
        """
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                raw_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        raw_parts.append(page_text)
                raw_text = '\n'.join(raw_parts)

                filename = Path(file_path).name
                logger.info(f"[PDF原始提取] {filename} ({len(raw_text)} 字符)\n{raw_text}")

                return raw_text

        except ImportError:
            logger.error("pdfplumber 未安装，请执行: pip install pdfplumber")
            raise ParseError("pdfplumber 未安装，无法提取 PDF 文本")
        except Exception as e:
            logger.error(f"PDF 文本提取失败: {file_path}, 错误: {e}")
            raise ParseError(f"PDF 文本提取失败: {e}")

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
