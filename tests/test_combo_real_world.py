"""智能凑票实际场景测试 - 验证用户报告的问题已修复"""

import pytest
from unittest.mock import patch
from models.invoice import Invoice
from services.combo_service import ComboService, ComboParams


@pytest.fixture
def combo_service():
    """创建凑票服务实例"""
    return ComboService()


class TestRealWorldScenario:
    """测试实际场景 - 目标金额11111元"""
    
    def test_target_11111_no_extreme_solutions(self, combo_service):
        """
        测试目标金额11111元，确保不会出现极端不合理的方案
        用户报告的问题：有些方案给到了20000以上，或者3800的总金额
        """
        # 创建一组真实的发票数据，总金额约20000元
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=3200.0, business_type="餐饮", reimbursement_status="未报销"),
            Invoice(id=2, invoice_number="INV002", total_amount=2800.0, business_type="交通", reimbursement_status="未报销"),
            Invoice(id=3, invoice_number="INV003", total_amount=4500.0, business_type="住宿", reimbursement_status="未报销"),
            Invoice(id=4, invoice_number="INV004", total_amount=1800.0, business_type="办公", reimbursement_status="未报销"),
            Invoice(id=5, invoice_number="INV005", total_amount=2200.0, business_type="餐饮", reimbursement_status="未报销"),
            Invoice(id=6, invoice_number="INV006", total_amount=1500.0, business_type="交通", reimbursement_status="未报销"),
            Invoice(id=7, invoice_number="INV007", total_amount=3800.0, business_type="住宿", reimbursement_status="未报销"),
            Invoice(id=8, invoice_number="INV008", total_amount=2900.0, business_type="办公", reimbursement_status="未报销"),
        ]
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            # 测试 greater 模式
            params = ComboParams(
                target_amount=11111.0,
                amount_mode="greater",
                strategy="fewest",
                max_solutions=10
            )
            solutions = combo_service.find_combinations(params)
            
            # 应该有方案
            assert len(solutions) > 0, "应该找到至少一个方案"
            
            # 计算智能阈值（与算法一致）
            diff_threshold = max(11111.0 * 0.15, 2000.0)  # 2000.0
            
            # 验证每个方案的合理性
            for i, sol in enumerate(solutions):
                abs_diff = abs(sol.difference)
                
                # 核心断言：差额不应超过阈值
                assert abs_diff <= diff_threshold, \
                    f"方案{i+1} 差额 ¥{abs_diff:.2f} 超出阈值 ¥{diff_threshold:.2f}，" \
                    f"总金额=¥{sol.total_amount:.2f}，目标=¥11111.00"
                
                # 额外检查：不应出现极端值
                # 不应超过 20000（目标 + 阈值）
                assert sol.total_amount <= 11111.0 + diff_threshold, \
                    f"方案{i+1} 总金额 ¥{sol.total_amount:.2f} 过高，不应超过 ¥{11111.0 + diff_threshold:.2f}"
                
                # 不应低于 3800（这是用户报告的另一个问题）
                # 实际上阈值已经保证了这一点，但我们明确检查
                assert sol.total_amount >= 11111.0 - diff_threshold, \
                    f"方案{i+1} 总金额 ¥{sol.total_amount:.2f} 过低，不应低于 ¥{11111.0 - diff_threshold:.2f}"
                
                print(f"方案{i+1}: {sol.count}张, 合计=¥{sol.total_amount:.2f}, "
                      f"差额=¥{sol.difference:+.2f} ✓")
    
    def test_target_11111_less_mode(self, combo_service):
        """测试目标金额11111元，less模式（可少于）"""
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=3200.0, reimbursement_status="未报销"),
            Invoice(id=2, invoice_number="INV002", total_amount=2800.0, reimbursement_status="未报销"),
            Invoice(id=3, invoice_number="INV003", total_amount=4500.0, reimbursement_status="未报销"),
            Invoice(id=4, invoice_number="INV004", total_amount=1800.0, reimbursement_status="未报销"),
            Invoice(id=5, invoice_number="INV005", total_amount=2200.0, reimbursement_status="未报销"),
        ]
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            params = ComboParams(
                target_amount=11111.0,
                amount_mode="less",  # 可少于
                strategy="fewest",
                max_solutions=10
            )
            solutions = combo_service.find_combinations(params)
            
            # 所有方案的差额应该 <= 0（不超过目标）
            for i, sol in enumerate(solutions):
                assert sol.difference <= 0.01, \
                    f"方案{i+1} 在'可少于'模式下差额应≤0，实际=¥{sol.difference:+.2f}"
                
                print(f"方案{i+1} (less): {sol.count}张, 合计=¥{sol.total_amount:.2f}, "
                      f"差额=¥{sol.difference:+.2f} ✓")
    
    def test_target_11111_greater_mode(self, combo_service):
        """测试目标金额11111元，greater模式（可大于）"""
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=3200.0, reimbursement_status="未报销"),
            Invoice(id=2, invoice_number="INV002", total_amount=2800.0, reimbursement_status="未报销"),
            Invoice(id=3, invoice_number="INV003", total_amount=4500.0, reimbursement_status="未报销"),
            Invoice(id=4, invoice_number="INV004", total_amount=1800.0, reimbursement_status="未报销"),
            Invoice(id=5, invoice_number="INV005", total_amount=2200.0, reimbursement_status="未报销"),
        ]
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            params = ComboParams(
                target_amount=11111.0,
                amount_mode="greater",  # 可大于
                strategy="fewest",
                max_solutions=10
            )
            solutions = combo_service.find_combinations(params)
            
            # 所有方案的差额应该 >= 0（不小于目标）
            for i, sol in enumerate(solutions):
                assert sol.difference >= -0.01, \
                    f"方案{i+1} 在'可大于'模式下差额应≥0，实际=¥{sol.difference:+.2f}"
                
                print(f"方案{i+1} (greater): {sol.count}张, 合计=¥{sol.total_amount:.2f}, "
                      f"差额=¥{sol.difference:+.2f} ✓")
    
    def test_quality_filtering(self, combo_service):
        """测试质量过滤：确保返回的方案都是优质的"""
        # 创建大量发票，总金额远超目标
        invoices = [
            Invoice(id=i, invoice_number=f"INV{i:03d}", total_amount=1000.0 + i * 100, 
                   reimbursement_status="未报销")
            for i in range(20)
        ]
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            params = ComboParams(
                target_amount=5000.0,
                amount_mode="less",
                strategy="fewest",
                max_solutions=10
            )
            solutions = combo_service.find_combinations(params)
            
            # 计算阈值
            diff_threshold = max(5000.0 * 0.15, 2000.0)  # 2000.0
            
            # 所有方案都应在阈值范围内
            for i, sol in enumerate(solutions):
                abs_diff = abs(sol.difference)
                assert abs_diff <= diff_threshold, \
                    f"方案{i+1} 差额 ¥{abs_diff:.2f} 超出质量阈值"
            
            # 应该找到接近目标的方案
            if solutions:
                best_diff = min(abs(sol.difference) for sol in solutions)
                print(f"最优方案差额: ¥{best_diff:.2f} (阈值: ¥{diff_threshold:.2f})")
                assert best_diff < diff_threshold, "应该找到接近目标的优质方案"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
