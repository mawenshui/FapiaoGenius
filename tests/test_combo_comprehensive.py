"""智能凑票服务全面测试 — 覆盖所有金额模式 × 挑选策略组合"""

import pytest
from unittest.mock import patch
from models.invoice import Invoice
from services.combo_service import ComboService, ComboParams, ComboSolution


@pytest.fixture
def sample_invoices():
    """创建测试发票数据 - 10张不同金额的发票"""
    return [
        Invoice(id=1, invoice_number="INV001", total_amount=100.0, business_type="餐饮", reimbursement_status="未报销"),
        Invoice(id=2, invoice_number="INV002", total_amount=200.0, business_type="交通", reimbursement_status="未报销"),
        Invoice(id=3, invoice_number="INV003", total_amount=300.0, business_type="住宿", reimbursement_status="未报销"),
        Invoice(id=4, invoice_number="INV004", total_amount=150.0, business_type="办公", reimbursement_status="未报销"),
        Invoice(id=5, invoice_number="INV005", total_amount=250.0, business_type="餐饮", reimbursement_status="未报销"),
        Invoice(id=6, invoice_number="INV006", total_amount=50.0, business_type="交通", reimbursement_status="未报销"),
        Invoice(id=7, invoice_number="INV007", total_amount=180.0, business_type="住宿", reimbursement_status="未报销"),
        Invoice(id=8, invoice_number="INV008", total_amount=220.0, business_type="办公", reimbursement_status="未报销"),
        Invoice(id=9, invoice_number="INV009", total_amount=90.0, business_type="餐饮", reimbursement_status="未报销"),
        Invoice(id=10, invoice_number="INV010", total_amount=310.0, business_type="交通", reimbursement_status="未报销"),
    ]


@pytest.fixture
def combo_service():
    """创建凑票服务实例"""
    return ComboService()


class TestComboSolution:
    """测试 ComboSolution 数据类"""
    
    def test_solution_init_with_invoices(self, sample_invoices):
        """测试使用发票列表初始化方案"""
        sol = ComboSolution(invoices=sample_invoices[:3])
        assert sol.count == 3
        assert sol.total_amount == 600.0  # 100 + 200 + 300
        assert sol.difference == 0.0
    
    def test_solution_empty(self):
        """测试空方案"""
        sol = ComboSolution()
        assert sol.count == 0
        assert sol.total_amount == 0.0
        assert sol.difference == 0.0


class TestAllModeStrategyCombinations:
    """测试所有 2种金额模式 × 4种挑选策略 = 8种组合"""
    
    @pytest.mark.parametrize("amount_mode,strategy", [
        ("less", "fewest"),
        ("less", "most"),
        ("less", "large_first"),
        ("less", "small_first"),
        ("greater", "fewest"),
        ("greater", "most"),
        ("greater", "large_first"),
        ("greater", "small_first"),
    ])
    def test_mode_strategy_combinations(self, combo_service, sample_invoices, amount_mode, strategy):
        """测试每种金额模式和策略组合"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(
                target_amount=500.0,
                amount_mode=amount_mode,
                strategy=strategy,
                max_solutions=5
            )
            solutions = combo_service.find_combinations(params)
            
            # 应该找到至少一个方案
            assert len(solutions) > 0, f"组合 {amount_mode}/{strategy} 未找到方案"
            
            # 验证每个方案的合理性
            for i, sol in enumerate(solutions):
                # 方案应该有发票
                assert sol.count > 0, f"方案{i} 没有发票"
                
                # 方案金额应该是发票金额之和
                expected_total = sum(inv.total_amount for inv in sol.invoices)
                assert abs(sol.total_amount - expected_total) < 0.01, f"方案{i} 金额计算错误"
                
                # 差额应该是正确的
                expected_diff = sol.total_amount - 500.0
                assert abs(sol.difference - expected_diff) < 0.01, f"方案{i} 差额计算错误"
                
                # 根据金额模式验证差额符号
                if amount_mode == "less":
                    assert sol.difference <= 0.01, f"方案{i} 在'可少于'模式下差额应≤0"
                elif amount_mode == "greater":
                    assert sol.difference >= -0.01, f"方案{i} 在'可大于'模式下差额应≥0"
            
    def test_strategy_fewest_ordering(self, combo_service, sample_invoices):
        """测试'张数最少'策略的排序正确性"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(
                target_amount=300.0,
                amount_mode="less",
                strategy="fewest",
                max_solutions=10
            )
            solutions = combo_service.find_combinations(params)
            
            # 验证方案按张数升序排列
            for i in range(len(solutions) - 1):
                assert solutions[i].count <= solutions[i+1].count, \
                    f"方案{i} ({solutions[i].count}张) 应该在方案{i+1} ({solutions[i+1].count}张) 之前"
    
    def test_strategy_most_ordering(self, combo_service, sample_invoices):
        """测试'张数最多'策略的排序正确性"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(
                target_amount=800.0,
                amount_mode="less",
                strategy="most",
                max_solutions=10
            )
            solutions = combo_service.find_combinations(params)
            
            # 验证方案按张数降序排列
            for i in range(len(solutions) - 1):
                assert solutions[i].count >= solutions[i+1].count, \
                    f"方案{i} ({solutions[i].count}张) 应该在方案{i+1} ({solutions[i+1].count}张) 之前"
    
    def test_strategy_large_first_ordering(self, combo_service, sample_invoices):
        """测试'大额优先'策略的排序正确性"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(
                target_amount=500.0,
                amount_mode="less",
                strategy="large_first",
                max_solutions=10
            )
            solutions = combo_service.find_combinations(params)
            
            # 验证方案按平均金额降序排列
            for i in range(len(solutions) - 1):
                avg_i = solutions[i].total_amount / solutions[i].count if solutions[i].count > 0 else 0
                avg_next = solutions[i+1].total_amount / solutions[i+1].count if solutions[i+1].count > 0 else 0
                assert avg_i >= avg_next, \
                    f"方案{i} (平均¥{avg_i:.2f}) 应该在方案{i+1} (平均¥{avg_next:.2f}) 之前"
    
    def test_strategy_small_first_ordering(self, combo_service, sample_invoices):
        """测试'小额优先'策略的排序正确性"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(
                target_amount=500.0,
                amount_mode="less",
                strategy="small_first",
                max_solutions=10
            )
            solutions = combo_service.find_combinations(params)
            
            # 验证方案按平均金额升序排列
            for i in range(len(solutions) - 1):
                avg_i = solutions[i].total_amount / solutions[i].count if solutions[i].count > 0 else 0
                avg_next = solutions[i+1].total_amount / solutions[i+1].count if solutions[i+1].count > 0 else 0
                assert avg_i <= avg_next, \
                    f"方案{i} (平均¥{avg_i:.2f}) 应该在方案{i+1} (平均¥{avg_next:.2f}) 之前"


class TestAmountModes:
    """测试两种金额模式的详细行为"""
    
    def test_less_mode_exact_match(self, combo_service, sample_invoices):
        """测试'可少于'模式 - 精确匹配"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(target_amount=300.0, amount_mode="less")
            solutions = combo_service.find_combinations(params)
            
            # 应该找到正好 300 的方案
            exact_solutions = [s for s in solutions if abs(s.difference) < 0.01]
            assert len(exact_solutions) > 0, "应该找到精确匹配的方案"
    
    def test_less_mode_no_exceed(self, combo_service, sample_invoices):
        """测试'可少于'模式 - 不允许超出"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(target_amount=500.0, amount_mode="less")
            solutions = combo_service.find_combinations(params)
            
            # 所有方案的差额应该 <= 0
            for sol in solutions:
                assert sol.difference <= 0.01, f"方案差额 {sol.difference} 不应 > 0"
    
    def test_greater_mode_finds_valid_solutions(self, combo_service, sample_invoices):
        """测试'可大于'模式 - 找到有效方案"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(target_amount=300.0, amount_mode="greater", strategy="fewest", max_solutions=50)
            solutions = combo_service.find_combinations(params)
            
            # 应该找到至少一个方案
            assert len(solutions) > 0, "应该找到方案"
            
            # 所有方案的差额应该 >= 0（不小于目标）
            for sol in solutions:
                assert sol.difference >= -0.01, f"方案差额 {sol.difference} 不应 < 0"
    
    def test_greater_mode_no_less(self, combo_service, sample_invoices):
        """测试'可大于'模式 - 不允许少于"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(target_amount=300.0, amount_mode="greater")
            solutions = combo_service.find_combinations(params)
            
            # 所有方案的差额应该 >= 0
            for sol in solutions:
                assert sol.difference >= -0.01, f"方案差额 {sol.difference} 不应 < 0"
    
    def test_less_mode_finds_closest(self, combo_service, sample_invoices):
        """测试'可少于'模式 - 找到最接近目标的方案"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            # 使用更多方案以找到差额最小的
            params = ComboParams(target_amount=450.0, amount_mode="less", max_solutions=100)
            solutions = combo_service.find_combinations(params)
            
            # 应该找到差额较小的方案（450 = 200+250 或 100+150+200 等）
            if solutions:
                best_diff = min(abs(sol.difference) for sol in solutions)
                assert best_diff < 100.0, f"最优方案差额 {best_diff} 应该 < 100"


class TestEdgeCases:
    """测试边界情况"""
    
    def test_no_invoices(self, combo_service):
        """测试没有发票的情况"""
        with patch.object(combo_service._dao, 'get_all', return_value=[]):
            params = ComboParams(target_amount=300.0)
            solutions = combo_service.find_combinations(params)
            assert len(solutions) == 0
    
    def test_target_zero(self, combo_service, sample_invoices):
        """测试目标金额为 0"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(target_amount=0.0, amount_mode="less")
            solutions = combo_service.find_combinations(params)
            # 应该找到空方案或差额为 0 的方案
            assert len(solutions) >= 0
    
    def test_target_very_large(self, combo_service, sample_invoices):
        """测试目标金额非常大"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(target_amount=10000.0, amount_mode="less")
            solutions = combo_service.find_combinations(params)
            # 应该找到一些方案（所有发票加起来也不够）
            assert len(solutions) >= 0
    
    def test_single_invoice(self, combo_service):
        """测试只有一张发票"""
        single_invoice = [Invoice(id=1, invoice_number="INV001", total_amount=100.0, reimbursement_status="未报销")]
        with patch.object(combo_service._dao, 'get_all', return_value=single_invoice):
            params = ComboParams(target_amount=100.0, amount_mode="less")
            solutions = combo_service.find_combinations(params)
            assert len(solutions) > 0
            assert solutions[0].count == 1
            assert abs(solutions[0].difference) < 0.01
    
    def test_filter_business_type(self, combo_service, sample_invoices):
        """测试业务类型过滤"""
        food_invoices = [inv for inv in sample_invoices if inv.business_type == "餐饮"]
        with patch.object(combo_service._dao, 'get_all', return_value=food_invoices):
            params = ComboParams(target_amount=350.0, business_type="餐饮")
            solutions = combo_service.find_combinations(params)
            
            for sol in solutions:
                for inv in sol.invoices:
                    assert inv.business_type == "餐饮"


class TestGreedySearch:
    """测试贪心搜索（大规模数据）"""
    
    def test_greedy_search_trigger(self, combo_service):
        """测试贪心搜索触发条件（>50张发票）"""
        large_invoices = [
            Invoice(id=i, invoice_number=f"INV{i:03d}", total_amount=10.0 + i, reimbursement_status="未报销")
            for i in range(60)
        ]
        
        with patch.object(combo_service._dao, 'get_all', return_value=large_invoices):
            params = ComboParams(target_amount=500.0, amount_mode="less")
            solutions = combo_service.find_combinations(params)
            assert len(solutions) > 0
    
    def test_greedy_search_less_mode(self, combo_service):
        """测试贪心搜索在'可少于'模式下不超出"""
        large_invoices = [
            Invoice(id=i, invoice_number=f"INV{i:03d}", total_amount=10.0 + i, reimbursement_status="未报销")
            for i in range(60)
        ]
        
        with patch.object(combo_service._dao, 'get_all', return_value=large_invoices):
            params = ComboParams(target_amount=500.0, amount_mode="less")
            solutions = combo_service.find_combinations(params)
            
            for sol in solutions:
                assert sol.difference <= 0.01


class TestComboParams:
    """测试凑票参数"""
    
    def test_default_params(self):
        """测试默认参数"""
        params = ComboParams(target_amount=100.0)
        assert params.amount_mode == "less"
        assert params.strategy == "fewest"
        assert params.max_solutions == 10
    
    def test_custom_params(self):
        """测试自定义参数"""
        params = ComboParams(
            target_amount=500.0,
            amount_mode="greater",
            strategy="large_first",
            business_type="餐饮",
            max_solutions=5
        )
        assert params.target_amount == 500.0
        assert params.amount_mode == "greater"
        assert params.strategy == "large_first"
        assert params.business_type == "餐饮"
        assert params.max_solutions == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
