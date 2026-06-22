"""发票导入服务"""

from dataclasses import dataclass, field
from typing import Callable, Optional
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from parsers.parser_registry import create_registry, ParserRegistry
from database.invoice_dao import invoice_dao
from services.rule_service import rule_service
from models.invoice import Invoice
from core.exceptions import ParseError, DuplicateInvoiceError, RuleMatchError
from core.logger import logger
from utils.file_utils import get_file_name, is_supported_file, get_files_from_folder


@dataclass
class FailedFile:
    """失败文件信息"""
    file_path: str
    file_name: str
    reason: str
    is_rule_mismatch: bool = False


@dataclass
class ImportResult:
    """导入结果"""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    failed_details: list[FailedFile] = field(default_factory=list)


class ImportWorker(QThread):
    """导入工作线程"""
    
    progress = pyqtSignal(int, int, str)  # current, total, filename
    finished_signal = pyqtSignal(object)  # ImportResult
    
    def __init__(self, file_paths: list[str], import_service: 'ImportService'):
        super().__init__()
        self.file_paths = file_paths
        self.import_service = import_service
        self._cancelled = False
    
    def run(self):
        """执行导入"""
        result = self.import_service.import_files(
            self.file_paths,
            progress_callback=self.progress.emit,
            cancel_check=lambda: self._cancelled
        )
        self.finished_signal.emit(result)
    
    def cancel(self):
        """取消导入"""
        self._cancelled = True


class ImportService(QObject):
    """发票导入服务"""
    
    progress_updated = pyqtSignal(int, int, str)  # current, total, filename
    import_finished = pyqtSignal(object)  # ImportResult
    
    def __init__(self):
        super().__init__()
        self._registry: Optional[ParserRegistry] = None
        self._worker: Optional[ImportWorker] = None
    
    @property
    def registry(self) -> ParserRegistry:
        """获取解析器注册表"""
        if self._registry is None:
            self._registry = create_registry(rule_service)
        return self._registry
    
    def import_files(
        self,
        file_paths: list[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> ImportResult:
        """
        同步导入文件
        
        Args:
            file_paths: 文件路径列表
            progress_callback: 进度回调 (current, total, filename)
            cancel_check: 取消检查函数
            
        Returns:
            ImportResult: 导入结果
        """
        result = ImportResult(total=len(file_paths))
        
        for i, file_path in enumerate(file_paths):
            # 检查是否取消
            if cancel_check and cancel_check():
                logger.info("导入已取消")
                break
            
            # 更新进度
            if progress_callback:
                progress_callback(i + 1, result.total, get_file_name(file_path))
            
            try:
                # 检查文件格式
                if not is_supported_file(file_path):
                    result.failed += 1
                    result.failed_details.append(FailedFile(
                        file_path=file_path,
                        file_name=get_file_name(file_path),
                        reason="不支持的文件格式"
                    ))
                    continue
                
                # 解析文件
                logger.debug(f"[导入] 开始解析: {get_file_name(file_path)}")
                invoice = self.registry.parse(file_path)
                logger.debug(
                    f"[导入] 解析完成: {get_file_name(file_path)}, "
                    f"发票号码={invoice.invoice_number}, "
                    f"购买方={invoice.buyer_name}, 销售方={invoice.seller_name}, "
                    f"不含税={invoice.amount_without_tax}, 税额={invoice.tax_amount}, "
                    f"价税合计={invoice.total_amount}"
                )
                
                # 检查发票号码是否为空（无法提取号码时视为解析失败）
                if not invoice.invoice_number or not invoice.invoice_number.strip():
                    result.failed += 1
                    result.failed_details.append(FailedFile(
                        file_path=file_path,
                        file_name=get_file_name(file_path),
                        reason="无法提取发票号码",
                        is_rule_mismatch=True
                    ))
                    continue
                
                # 检查重复（仅对有有效号码的发票）
                if invoice_dao.exists_by_number(invoice.invoice_number):
                    result.skipped += 1
                    continue
                
                # 设置导入时间
                invoice.set_import_time()
                
                # 保存到数据库
                invoice_dao.insert(invoice)
                result.success += 1
                logger.debug(f"[导入] 入库成功: {get_file_name(file_path)}, ID={invoice.id}")
                
            except DuplicateInvoiceError:
                result.skipped += 1
            except RuleMatchError as e:
                result.failed += 1
                result.failed_details.append(FailedFile(
                    file_path=file_path,
                    file_name=get_file_name(file_path),
                    reason=str(e),
                    is_rule_mismatch=True
                ))
            except ParseError as e:
                result.failed += 1
                result.failed_details.append(FailedFile(
                    file_path=file_path,
                    file_name=get_file_name(file_path),
                    reason=str(e),
                    is_rule_mismatch='规则' in str(e) or '格式' in str(e)
                ))
            except Exception as e:
                result.failed += 1
                result.failed_details.append(FailedFile(
                    file_path=file_path,
                    file_name=get_file_name(file_path),
                    reason=f"未知错误: {e}"
                ))
                logger.error(f"导入文件失败: {file_path}, 错误: {e}")
        
        logger.info(f"导入完成: 总计 {result.total}, 成功 {result.success}, "
                   f"失败 {result.failed}, 跳过 {result.skipped}")
        return result
    
    def import_files_async(self, file_paths: list[str]):
        """
        异步导入文件
        
        Args:
            file_paths: 文件路径列表
        """
        if self._worker and self._worker.isRunning():
            logger.warning("导入任务正在运行中")
            return
        
        self._worker = ImportWorker(file_paths, self)
        self._worker.progress.connect(self.progress_updated.emit)
        self._worker.finished_signal.connect(self.import_finished.emit)
        self._worker.start()
    
    def cancel_import(self):
        """取消导入"""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            logger.info("正在取消导入...")
    
    def import_folder(self, folder_path: str) -> list[str]:
        """
        从文件夹获取文件列表
        
        Args:
            folder_path: 文件夹路径
            
        Returns:
            list[str]: 文件路径列表
        """
        return get_files_from_folder(folder_path)


# 全局导入服务实例
import_service = ImportService()
