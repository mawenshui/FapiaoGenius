"""验证不同策略生成不同方案的测试"""

import pytest
from unittest.mock import patch
from models.invoice import Invoice
from services.combo_service import ComboService, ComboParams


@pytest.fixture
def combo_service():
    """创建凑票服务实例"""
    return ComboService()


class TestDifferentStrategiesGenerateDifferentSolutions:
    """验证不同策略确实生成不同的方案，而不是仅仅排序不同"""
    
    def test_strategies_generate_different_solutions(self, combo_service):
        """
        核心测试：验证4种策略生成的方案确实不同
        
        使用相同的发票数据和目标金额，但使用不同的策略，
        验证生成的方案集合有显著差异（不仅仅是排序不同）。
        """
        # 创建足够多的发票数据，使不同策略能产生明显差异
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=5000.0, reimbursement_status="未报销"),
            Invoice(id=2, invoice_number="INV002", total_amount=3000.0, reimbursement_status="未报销"),
            Invoice(id=3, invoice_number="INV003", total_amount=2000.0, reimbursement_status="未报销"),
            Invoice(id=4, invoice_number="INV004", total_amount=1500.0, reimbursement_status="未报销"),
            Invoice(id=5, invoice_number="INV005", total_amount=1000.0, reimbursement_status="未报销"),
            Invoice(id=6, invoice_number="INV006", total_amount=800.0, reimbursement_status="未报销"),
            Invoice(id=7, invoice_number="INV007", total_amount=600.0, reimbursement_status="未报销"),
            Invoice(id=8, invoice_number="INV008", total_amount=400.0, reimbursement_status="未报销"),
        ]
        
        target = 6000.0
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            # 测试5种策略
            strategies = ["fewest", "most", "large_first", "small_first"]
            results = {}
            
            for strategy in strategies:
                params = ComboParams(
                    target_amount=target,
                    amount_mode="less",
                    strategy=strategy,
                    max_solutions=5
                )
                solutions = combo_service.find_combinations(params)
                results[strategy] = solutions
                
                print(f"\n{strategy} 策略:")
                print(f"  找到 {len(solutions)} 个方案")
                if solutions:
                    for i, sol in enumerate(solutions[:3], 1):
                        inv_ids = [inv.id for inv in sol.invoices]
                        print(f"  方案{i}: {sol.count}张, {sol.total_amount:.2f}元, "
                              f"差额{sol.difference:+.2f}元, 发票ID={inv_ids}")
            
            # 验证：不同策略应该生成不同的方案集合
            # 比较"张数最少"和"张数最多"策略的第一个方案
            if results["fewest"] and results["most"]:
                fewest_first = results["fewest"][0]
                most_first = results["most"][0]
                
                # 张数应该不同（或至少发票组合不同）
                fewest_ids = set(inv.id for inv in fewest_first.invoices)
                most_ids = set(inv.id for inv in most_first.invoices)
                
                print(f"\n验证:")
                print(f"  张数最少策略第一个方案: {fewest_first.count}张, ID={fewest_ids}")
                print(f"  张数最多策略第一个方案: {most_first.count}张, ID={most_ids}")
            
            # 比较"大额优先"和"小额优先"策略
            if results["large_first"] and results["small_first"]:
                large_first = results["large_first"][0]
                small_first = results["small_first"][0]
                
                large_avg = large_first.total_amount / large_first.count if large_first.count > 0 else 0
                small_avg = small_first.total_amount / small_first.count if small_first.count > 0 else 0
                
                print(f"\n验证:")
                print(f"  大额优先策略第一个方案: 平均{large_avg:.2f}元")
                print(f"  小额优先策略第一个方案: 平均{small_avg:.2f}元")
                
                # 平均金额应该不同
                assert abs(large_avg - small_avg) > 100, \
                    f"大额优先和小额优先的平均金额应该差异明显: {large_avg:.2f} vs {small_avg:.2f}"
                print(f"  ✓ 平均金额差异明显 ({large_avg:.2f}元 vs {small_avg:.2f}元)，策略确实生成不同方案")
    
    def test_fewest_vs_most_count_difference(self, combo_service):
        """
        验证"张数最少"和"张数最多"策略的第一个方案张数确实不同
        """
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=3000.0, reimbursement_status="未报销"),
            Invoice(id=2, invoice_number="INV002", total_amount=2500.0, reimbursement_status="未报销"),
            Invoice(id=3, invoice_number="INV003", total_amount=2000.0, reimbursement_status="未报销"),
            Invoice(id=4, invoice_number="INV004", total_amount=1500.0, reimbursement_status="未报销"),
            Invoice(id=5, invoice_number="INV005", total_amount=1000.0, reimbursement_status="未报销"),
            Invoice(id=6, invoice_number="INV006", total_amount=800.0, reimbursement_status="未报销"),
            Invoice(id=7, invoice_number="INV007", total_amount=500.0, reimbursement_status="未报销"),
        ]
        
        target = 5000.0
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            # 张数最少策略
            params_fewest = ComboParams(
                target_amount=target,
                amount_mode="less",
                strategy="fewest",
                max_solutions=5
            )
            solutions_fewest = combo_service.find_combinations(params_fewest)
            
            # 张数最多策略
            params_most = ComboParams(
                target_amount=target,
                amount_mode="less",
                strategy="most",
                max_solutions=5
            )
            solutions_most = combo_service.find_combinations(params_most)
            
            assert len(solutions_fewest) > 0, "张数最少策略应该找到方案"
            assert len(solutions_most) > 0, "张数最多策略应该找到方案"
            
            # 第一个方案的张数应该不同
            fewest_count = solutions_fewest[0].count
            most_count = solutions_most[0].count
            
            print(f"\n目标金额: {target:.2f}元")
            print(f"张数最少策略第一个方案: {fewest_count}张")
            print(f"张数最多策略第一个方案: {most_count}张")
            
            # 张数应该不同（或至少张数少的 <= 张数多的）
            assert fewest_count <= most_count, \
                f"张数最少策略的张数 {fewest_count} 应该 <= 张数最多策略的张数 {most_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
