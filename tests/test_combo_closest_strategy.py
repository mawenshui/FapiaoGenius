"""测试所有策略都内置差额最小行为"""

import pytest
from unittest.mock import patch
from models.invoice import Invoice
from services.combo_service import ComboService, ComboParams


@pytest.fixture
def combo_service():
    """创建凑票服务实例"""
    return ComboService()


class TestAllStrategiesMinimizeDifference:
    """验证所有策略都内置差额最小行为"""
    
    def test_all_strategies_find_close_solutions_greater_mode(self, combo_service):
        """
        验证在"可大于"模式下，所有策略都能找到差额较小的方案
        """
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=3200.0, reimbursement_status="未报销"),
            Invoice(id=2, invoice_number="INV002", total_amount=2800.0, reimbursement_status="未报销"),
            Invoice(id=3, invoice_number="INV003", total_amount=4500.0, reimbursement_status="未报销"),
            Invoice(id=4, invoice_number="INV004", total_amount=1800.0, reimbursement_status="未报销"),
            Invoice(id=5, invoice_number="INV005", total_amount=2200.0, reimbursement_status="未报销"),
            Invoice(id=6, invoice_number="INV006", total_amount=1500.0, reimbursement_status="未报销"),
            Invoice(id=7, invoice_number="INV007", total_amount=3800.0, reimbursement_status="未报销"),
            Invoice(id=8, invoice_number="INV008", total_amount=2900.0, reimbursement_status="未报销"),
        ]
        
        strategies = ["fewest", "most", "large_first", "small_first"]
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            for strategy in strategies:
                params = ComboParams(
                    target_amount=11111.0,
                    amount_mode="greater",
                    strategy=strategy,
                    max_solutions=10
                )
                solutions = combo_service.find_combinations(params)
                
                # 每个策略都应该找到方案
                assert len(solutions) > 0, f"策略 {strategy} 应该找到至少一个方案"
                
                # 所有方案的差额都应该 >= 0（可大于模式）
                for sol in solutions:
                    assert sol.difference >= -0.01, \
                        f"策略 {strategy}: 方案差额 {sol.difference:+.2f} 应该 >= 0"
                
                # 最优方案的差额应该较小（验证差额最小行为）
                best_diff = abs(solutions[0].difference)
                assert best_diff < 500.0, \
                    f"策略 {strategy}: 最优方案差额 {best_diff:.2f} 应该 < 500（差额最小行为）"
    
    def test_all_strategies_find_close_solutions_less_mode(self, combo_service):
        """
        验证在"可少于"模式下，所有策略都能找到差额较小的方案
        """
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=3200.0, reimbursement_status="未报销"),
            Invoice(id=2, invoice_number="INV002", total_amount=2800.0, reimbursement_status="未报销"),
            Invoice(id=3, invoice_number="INV003", total_amount=4500.0, reimbursement_status="未报销"),
            Invoice(id=4, invoice_number="INV004", total_amount=1800.0, reimbursement_status="未报销"),
            Invoice(id=5, invoice_number="INV005", total_amount=2200.0, reimbursement_status="未报销"),
        ]
        
        strategies = ["fewest", "most", "large_first", "small_first"]
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            for strategy in strategies:
                params = ComboParams(
                    target_amount=5000.0,
                    amount_mode="less",
                    strategy=strategy,
                    max_solutions=10
                )
                solutions = combo_service.find_combinations(params)
                
                # 每个策略都应该找到方案
                assert len(solutions) > 0, f"策略 {strategy} 应该找到至少一个方案"
                
                # 所有方案的差额都应该 <= 0（可少于模式）
                for sol in solutions:
                    assert sol.difference <= 0.01, \
                        f"策略 {strategy}: 方案差额 {sol.difference:+.2f} 应该 <= 0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
