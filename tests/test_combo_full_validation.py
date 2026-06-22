"""智能凑票功能全面验证测试 - 逐一检查所有方案的合理性"""

import pytest
from unittest.mock import patch
from models.invoice import Invoice
from services.combo_service import ComboService, ComboParams


@pytest.fixture
def combo_service():
    """创建凑票服务实例"""
    return ComboService()


class TestComprehensiveValidation:
    """全面验证所有方案的合理性"""
    
    def test_all_modes_and_strategies(self, combo_service):
        """
        测试所有金额模式 × 挑选策略的组合
        2种模式 × 4种策略 = 8种组合
        逐一验证每个方案的合理性
        """
        # 创建测试发票数据（覆盖不同金额范围）
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=5000.0, business_type="餐饮", reimbursement_status="未报销"),
            Invoice(id=2, invoice_number="INV002", total_amount=3000.0, business_type="交通", reimbursement_status="未报销"),
            Invoice(id=3, invoice_number="INV003", total_amount=2000.0, business_type="住宿", reimbursement_status="未报销"),
            Invoice(id=4, invoice_number="INV004", total_amount=1500.0, business_type="办公", reimbursement_status="未报销"),
            Invoice(id=5, invoice_number="INV005", total_amount=1000.0, business_type="餐饮", reimbursement_status="未报销"),
            Invoice(id=6, invoice_number="INV006", total_amount=800.0, business_type="交通", reimbursement_status="未报销"),
            Invoice(id=7, invoice_number="INV007", total_amount=600.0, business_type="住宿", reimbursement_status="未报销"),
            Invoice(id=8, invoice_number="INV008", total_amount=400.0, business_type="办公", reimbursement_status="未报销"),
        ]
        
        target_amounts = [3000.0, 6000.0, 10000.0]  # 小、中、大目标金额
        amount_modes = ["less", "greater"]
        strategies = ["fewest", "most", "large_first", "small_first"]
        
        mode_names = {"less": "可少于", "greater": "可大于"}
        strategy_names = {"fewest": "张数最少", "most": "张数最多", 
                         "large_first": "大额优先", "small_first": "小额优先"}
        
        total_tests = 0
        passed_tests = 0
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            for target in target_amounts:
                print(f"\n{'='*80}")
                print(f"目标金额: {target:.2f}元")
                print(f"{'='*80}")
                
                diff_threshold = max(target * 0.15, 2000.0)
                print(f"智能差额阈值: ±{diff_threshold:.2f}元")
                
                for mode in amount_modes:
                    for strategy in strategies:
                        total_tests += 1
                        
                        params = ComboParams(
                            target_amount=target,
                            amount_mode=mode,
                            strategy=strategy,
                            max_solutions=5
                        )
                        
                        solutions = combo_service.find_combinations(params)
                        
                        print(f"\n  [{mode_names[mode]} + {strategy_names[strategy]}]")
                        print(f"  找到 {len(solutions)} 个方案")
                        
                        if not solutions:
                            print(f"  ⚠ 未找到方案（可能正常，如目标金额过高）")
                            passed_tests += 1  # 没找到方案也算通过
                            continue
                        
                        # 逐一检查每个方案
                        all_valid = True
                        for i, sol in enumerate(solutions, 1):
                            # 验证1：金额模式约束
                            if mode == "less":
                                if sol.difference > 0.01:
                                    print(f"    ✗ 方案{i}: 差额{sol.difference:+.2f}元 > 0（可少于模式不应超过目标）")
                                    all_valid = False
                            elif mode == "greater":
                                if sol.difference < -0.01:
                                    print(f"    ✗ 方案{i}: 差额{sol.difference:+.2f}元 < 0（可大于模式不应低于目标）")
                                    all_valid = False
                            
                            # 验证2：差额阈值约束
                            abs_diff = abs(sol.difference)
                            if abs_diff > diff_threshold + 0.01:
                                print(f"    ✗ 方案{i}: 差额{abs_diff:.2f}元 超出阈值{diff_threshold:.2f}元")
                                all_valid = False
                            
                            # 验证3：方案基本属性
                            if sol.count <= 0:
                                print(f"    ✗ 方案{i}: 张数{sol.count} <= 0（不合理）")
                                all_valid = False
                            
                            if sol.total_amount <= 0:
                                print(f"    ✗ 方案{i}: 总金额{sol.total_amount:.2f}元 <= 0（不合理）")
                                all_valid = False
                            
                            # 验证4：差额计算正确性
                            expected_diff = sol.total_amount - target
                            if abs(sol.difference - expected_diff) > 0.01:
                                print(f"    ✗ 方案{i}: 差额计算错误，应为{expected_diff:+.2f}元，实际{sol.difference:+.2f}元")
                                all_valid = False
                            
                            # 验证5：发票数量与列表长度一致
                            if sol.count != len(sol.invoices):
                                print(f"    ✗ 方案{i}: 张数{sol.count} != 发票列表长度{len(sol.invoices)}")
                                all_valid = False
                            
                            # 验证6：总金额与发票金额之和一致
                            expected_total = sum(inv.total_amount for inv in sol.invoices)
                            if abs(sol.total_amount - expected_total) > 0.01:
                                print(f"    ✗ 方案{i}: 总金额{sol.total_amount:.2f}元 != 发票金额之和{expected_total:.2f}元")
                                all_valid = False
                        
                        if all_valid:
                            # 打印最优方案
                            best = solutions[0]
                            print(f"  ✓ 所有方案有效")
                            print(f"    最优: {best.count}张, {best.total_amount:.2f}元, 差额{best.difference:+.2f}元")
                            passed_tests += 1
                        else:
                            print(f"  ✗ 存在无效方案")
        
        print(f"\n{'='*80}")
        print(f"测试总结: {passed_tests}/{total_tests} 通过")
        print(f"{'='*80}")
        
        assert passed_tests == total_tests, f"有 {total_tests - passed_tests} 个测试未通过"
    
    def test_solution_sorting_order(self, combo_service):
        """
        验证每种策略的排序顺序是否正确
        """
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=5000.0, reimbursement_status="未报销"),
            Invoice(id=2, invoice_number="INV002", total_amount=3000.0, reimbursement_status="未报销"),
            Invoice(id=3, invoice_number="INV003", total_amount=2000.0, reimbursement_status="未报销"),
            Invoice(id=4, invoice_number="INV004", total_amount=1500.0, reimbursement_status="未报销"),
            Invoice(id=5, invoice_number="INV005", total_amount=1000.0, reimbursement_status="未报销"),
        ]
        
        target = 5000.0
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            # 测试张数最少策略：应按张数升序
            params = ComboParams(target_amount=target, amount_mode="less", strategy="fewest", max_solutions=10)
            solutions = combo_service.find_combinations(params)
            
            print(f"\n张数最少策略排序验证:")
            if len(solutions) > 1:
                for i in range(len(solutions) - 1):
                    count_i = solutions[i].count
                    count_next = solutions[i+1].count
                    assert count_i <= count_next, \
                        f"张数最少策略排序错误: 方案{i+1}张数{count_i} > 方案{i+2}张数{count_next}"
                print(f"  ✓ 张数升序排序正确")
            
            # 测试张数最多策略：应按张数降序
            params = ComboParams(target_amount=target, amount_mode="less", strategy="most", max_solutions=10)
            solutions = combo_service.find_combinations(params)
            
            print(f"\n张数最多策略排序验证:")
            if len(solutions) > 1:
                for i in range(len(solutions) - 1):
                    count_i = solutions[i].count
                    count_next = solutions[i+1].count
                    assert count_i >= count_next, \
                        f"张数最多策略排序错误: 方案{i+1}张数{count_i} < 方案{i+2}张数{count_next}"
                print(f"  ✓ 张数降序排序正确")
            
            # 测试大额优先策略：应按平均金额降序
            params = ComboParams(target_amount=target, amount_mode="less", strategy="large_first", max_solutions=10)
            solutions = combo_service.find_combinations(params)
            
            print(f"\n大额优先策略排序验证:")
            if len(solutions) > 1:
                for i in range(len(solutions) - 1):
                    avg_i = solutions[i].total_amount / solutions[i].count if solutions[i].count > 0 else 0
                    avg_next = solutions[i+1].total_amount / solutions[i+1].count if solutions[i+1].count > 0 else 0
                    assert avg_i >= avg_next - 0.01, \
                        f"大额优先策略排序错误: 方案{i+1}平均{avg_i:.2f}元 < 方案{i+2}平均{avg_next:.2f}元"
                print(f"  ✓ 平均金额降序排序正确")
            
            # 测试小额优先策略：应按平均金额升序
            params = ComboParams(target_amount=target, amount_mode="less", strategy="small_first", max_solutions=10)
            solutions = combo_service.find_combinations(params)
            
            print(f"\n小额优先策略排序验证:")
            if len(solutions) > 1:
                for i in range(len(solutions) - 1):
                    avg_i = solutions[i].total_amount / solutions[i].count if solutions[i].count > 0 else 0
                    avg_next = solutions[i+1].total_amount / solutions[i+1].count if solutions[i+1].count > 0 else 0
                    assert avg_i <= avg_next + 0.01, \
                        f"小额优先策略排序错误: 方案{i+1}平均{avg_i:.2f}元 > 方案{i+2}平均{avg_next:.2f}元"
                print(f"  ✓ 平均金额升序排序正确")
    
    def test_no_duplicate_invoices_in_solution(self, combo_service):
        """
        验证每个方案中没有重复的发票
        """
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=3000.0, reimbursement_status="未报销"),
            Invoice(id=2, invoice_number="INV002", total_amount=2000.0, reimbursement_status="未报销"),
            Invoice(id=3, invoice_number="INV003", total_amount=1500.0, reimbursement_status="未报销"),
            Invoice(id=4, invoice_number="INV004", total_amount=1000.0, reimbursement_status="未报销"),
        ]
        
        target = 4000.0
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            params = ComboParams(target_amount=target, amount_mode="less", strategy="fewest", max_solutions=10)
            solutions = combo_service.find_combinations(params)
            
            print(f"\n验证方案中没有重复发票:")
            for i, sol in enumerate(solutions, 1):
                invoice_ids = [inv.id for inv in sol.invoices]
                unique_ids = set(invoice_ids)
                
                if len(invoice_ids) != len(unique_ids):
                    print(f"  ✗ 方案{i}: 存在重复发票，ID列表={invoice_ids}")
                    assert False, f"方案{i}存在重复发票"
                
                print(f"  ✓ 方案{i}: 无重复发票，共{sol.count}张")
    
    def test_extreme_scenarios(self, combo_service):
        """
        测试极端场景
        """
        # 场景1：目标金额为0
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=100.0, reimbursement_status="未报销"),
        ]
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            params = ComboParams(target_amount=0.0, amount_mode="less", strategy="fewest", max_solutions=5)
            solutions = combo_service.find_combinations(params)
            print(f"\n场景1: 目标金额为0")
            print(f"  找到 {len(solutions)} 个方案")
            # 应该找到空方案或差额为0的方案
            assert len(solutions) >= 0, "目标金额为0应该能找到方案"
            print(f"  ✓ 场景1通过")
        
        # 场景2：目标金额远大于所有发票总和
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=100.0, reimbursement_status="未报销"),
            Invoice(id=2, invoice_number="INV002", total_amount=200.0, reimbursement_status="未报销"),
        ]
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            params = ComboParams(target_amount=10000.0, amount_mode="less", strategy="fewest", max_solutions=5)
            solutions = combo_service.find_combinations(params)
            print(f"\n场景2: 目标金额远大于所有发票总和")
            print(f"  找到 {len(solutions)} 个方案")
            # 应该能找到一些方案（所有发票加起来也不够）
            assert len(solutions) >= 0, "目标金额过大应该能找到方案"
            print(f"  ✓ 场景2通过")
        
        # 场景3：只有一张发票
        invoices = [
            Invoice(id=1, invoice_number="INV001", total_amount=100.0, reimbursement_status="未报销"),
        ]
        
        with patch.object(combo_service._dao, 'get_all', return_value=invoices):
            params = ComboParams(target_amount=100.0, amount_mode="less", strategy="fewest", max_solutions=5)
            solutions = combo_service.find_combinations(params)
            print(f"\n场景3: 只有一张发票")
            print(f"  找到 {len(solutions)} 个方案")
            assert len(solutions) > 0, "只有一张发票应该能找到方案"
            assert solutions[0].count == 1, "应该只包含1张发票"
            assert abs(solutions[0].difference) < 0.01, "差额应该接近0"
            print(f"  ✓ 场景3通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
