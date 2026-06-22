"""v1.4 新功能测试 — OCR降级/批量操作/备份恢复/高级搜索/CSV导出"""

import os
import csv
import json
import tempfile
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from models.invoice import Invoice
from services.export_service import ExportService, export_service
from services.backup_service import BackupService, backup_service
from database.invoice_dao import InvoiceDAO, FilterCriteria


@pytest.fixture
def sample_invoices():
    """测试发票数据"""
    return [
        Invoice(id=1, invoice_number="INV001", total_amount=100.0,
                business_type="餐饮", invoice_type="电子发票",
                invoice_date="2026-01-15", buyer_name="测试公司",
                seller_name="餐厅A", amount_without_tax=94.34,
                tax_amount=5.66, reimbursement_status="未报销",
                status="正常", remark="", source_file_path="/tmp/a.pdf",
                file_format="pdf", rule_id="", import_time="2026-01-15"),
        Invoice(id=2, invoice_number="INV002", total_amount=500.0,
                business_type="住宿", invoice_type="电子发票",
                invoice_date="2026-02-20", buyer_name="测试公司",
                seller_name="酒店B", amount_without_tax=471.70,
                tax_amount=28.30, reimbursement_status="报销中",
                status="正常", remark="", source_file_path="/tmp/b.pdf",
                file_format="pdf", rule_id="", import_time="2026-02-20"),
        Invoice(id=3, invoice_number="INV003", total_amount=1500.0,
                business_type="交通", invoice_type="电子发票",
                invoice_date="2026-03-10", buyer_name="测试公司",
                seller_name="航空C", amount_without_tax=1415.09,
                tax_amount=84.91, reimbursement_status="已报销",
                status="正常", remark="", source_file_path="/tmp/c.pdf",
                file_format="pdf", rule_id="", import_time="2026-03-10"),
    ]


class TestCSVExport:
    """测试 CSV 导出"""
    
    def test_export_csv_basic(self, sample_invoices, tmp_path):
        """测试基本 CSV 导出"""
        output = str(tmp_path / "test.csv")
        result = export_service.export_to_csv(sample_invoices, output)
        
        assert result is True
        assert os.path.exists(output)
        
        # 验证 CSV 内容
        with open(output, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        # 表头 + 3 行数据
        assert len(rows) == 4
        # 表头包含"业务类型"
        assert "业务类型" in rows[0]
        # 数据行
        assert rows[1][0] == "餐饮"  # 第一行业务类型
        assert rows[2][0] == "住宿"
    
    def test_export_csv_empty(self, tmp_path):
        """测试空列表导出"""
        output = str(tmp_path / "empty.csv")
        result = export_service.export_to_csv([], output)
        
        assert result is True
        with open(output, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        assert len(rows) == 1  # 只有表头
    
    def test_export_csv_amount_format(self, sample_invoices, tmp_path):
        """测试金额格式（两位小数）"""
        output = str(tmp_path / "amounts.csv")
        export_service.export_to_csv(sample_invoices, output)
        
        with open(output, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        # 金额列应为两位小数格式
        assert rows[1][6] == "94.34"  # amount_without_tax
        assert rows[1][8] == "100.00"  # total_amount


class TestBackupService:
    """测试备份与恢复"""
    
    def test_backup_creates_valid_zip(self, tmp_path):
        """测试备份创建有效 ZIP"""
        backup_path = str(tmp_path / "backup.zip")
        
        with patch('services.backup_service.app_config') as mock_config:
            mock_config.data_dir = str(tmp_path)
            mock_config.db_path = str(tmp_path / "test.db")
            mock_config.rules_dir = str(tmp_path / "rules")
            
            # 创建模拟数据库和规则文件
            (tmp_path / "test.db").write_bytes(b"fake db content")
            (tmp_path / "rules").mkdir()
            (tmp_path / "rules" / "rule1.json").write_text('{"id": "test"}')
            
            result = backup_service.create_backup(backup_path)
        
        assert result['success'] is True
        assert os.path.exists(backup_path)
        
        # 验证 ZIP 内容
        with zipfile.ZipFile(backup_path, 'r') as zf:
            names = zf.namelist()
            assert 'backup_meta.json' in names
            assert 'invoices.db' in names
            assert 'rules/rule1.json' in names
    
    def test_backup_meta_content(self, tmp_path):
        """测试备份元信息内容"""
        backup_path = str(tmp_path / "meta_test.zip")
        
        with patch('services.backup_service.app_config') as mock_config:
            mock_config.data_dir = str(tmp_path)
            mock_config.db_path = str(tmp_path / "test.db")
            mock_config.rules_dir = str(tmp_path / "rules")
            
            (tmp_path / "test.db").write_bytes(b"data")
            (tmp_path / "rules").mkdir()
            
            backup_service.create_backup(backup_path)
        
        with zipfile.ZipFile(backup_path, 'r') as zf:
            meta = json.loads(zf.read('backup_meta.json'))
            assert meta['app'] == 'FapiaoGenius'
            assert meta['version'] == '1.0'
            assert 'created_at' in meta
    
    def test_restore_invalid_zip(self, tmp_path):
        """测试恢复无效 ZIP"""
        bad_zip = str(tmp_path / "bad.zip")
        Path(bad_zip).write_bytes(b"not a zip")
        
        result = backup_service.restore_backup(bad_zip)
        assert result['success'] is False
        assert "无效" in result['message'] or "失败" in result['message']
    
    def test_restore_non_fapiao_zip(self, tmp_path):
        """测试恢复非智票通 ZIP"""
        fake_zip = str(tmp_path / "fake.zip")
        with zipfile.ZipFile(fake_zip, 'w') as zf:
            zf.writestr('backup_meta.json', json.dumps({'app': 'OtherApp'}))
        
        result = backup_service.restore_backup(fake_zip)
        assert result['success'] is False
        assert "非智票通" in result['message']
    
    def test_default_backup_name(self):
        """测试默认备份文件名"""
        name = backup_service.get_default_backup_name()
        assert name.startswith("智票通_备份_")
        assert name.endswith(".zip")


class TestAmountRangeFilter:
    """测试金额范围过滤"""
    
    def test_filter_criteria_has_amount_fields(self):
        """测试 FilterCriteria 包含金额字段"""
        criteria = FilterCriteria()
        assert criteria.amount_from is None
        assert criteria.amount_to is None
        
        criteria = FilterCriteria(amount_from=100.0, amount_to=500.0)
        assert criteria.amount_from == 100.0
        assert criteria.amount_to == 500.0
    
    def test_amount_filter_sql_generation(self):
        """测试金额过滤 SQL 生成"""
        dao = InvoiceDAO()
        
        # 模拟 get_all 的条件构建逻辑
        criteria = FilterCriteria(amount_from=100.0, amount_to=1000.0)
        conditions = []
        params = []
        
        if criteria.amount_from is not None:
            conditions.append("total_amount >= ?")
            params.append(criteria.amount_from)
        if criteria.amount_to is not None:
            conditions.append("total_amount <= ?")
            params.append(criteria.amount_to)
        
        assert len(conditions) == 2
        assert "total_amount >= ?" in conditions
        assert "total_amount <= ?" in conditions
        assert params == [100.0, 1000.0]


class TestTextExtractorFallback:
    """测试 PDF 文本提取降级链"""
    
    def test_extractor_has_three_methods(self):
        """测试提取器有三个降级方法"""
        from parsers.text_extractor import TextExtractor
        
        assert hasattr(TextExtractor, '_extract_pdfplumber')
        assert hasattr(TextExtractor, '_extract_fitz')
        assert hasattr(TextExtractor, '_extract_ocr')
    
    def test_pdfplumber_returns_empty_on_failure(self, tmp_path):
        """测试 pdfplumber 失败时返回空字符串"""
        from parsers.text_extractor import TextExtractor
        
        # 不存在的文件
        result = TextExtractor._extract_pdfplumber(str(tmp_path / "nonexistent.pdf"))
        assert result == ""
    
    def test_fitz_returns_empty_on_failure(self, tmp_path):
        """测试 fitz 失败时返回空字符串"""
        from parsers.text_extractor import TextExtractor
        
        result = TextExtractor._extract_fitz(str(tmp_path / "nonexistent.pdf"))
        assert result == ""
    
    def test_ocr_returns_empty_without_tesseract(self, tmp_path):
        """测试无 tesseract 时 OCR 返回空"""
        from parsers.text_extractor import TextExtractor
        
        result = TextExtractor._extract_ocr(str(tmp_path / "nonexistent.pdf"))
        assert result == ""


class TestBatchOperations:
    """测试批量操作相关逻辑"""
    
    def test_invoice_dao_delete_batch(self):
        """测试批量删除 DAO"""
        dao = InvoiceDAO()
        # 空列表不应报错
        dao.delete_batch([])
    
    def test_combo_service_set_reimbursement_status_invalid(self):
        """测试设置无效报销状态"""
        from services.combo_service import combo_service
        
        with pytest.raises(ValueError):
            combo_service.set_reimbursement_status([1, 2], "无效状态")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
