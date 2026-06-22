"""智能凑票服务单元测试"""

import pytest
from unittest.mock import Mock, patch
from models.invoice import Invoice
from services.combo_service import ComboService, ComboParams, ComboSolution


@pytest.fixture
def sample_invoices():
    """创建测试发票数据"""
    return [
        Invoice(id=1, invoice_number="INV001", total_amount=100.0, business_type="餐饮", reimbursement_status="未报销"),
        Invoice(id=2, invoice_number="INV002", total_amount=200.0, business_type="交通", reimbursement_status="未报销"),
        Invoice(id=3, invoice_number="INV003", total_amount=300.0, business_type="住宿", reimbursement_status="未报销"),
        Invoice(id=4, invoice_number="INV004", total_amount=150.0, business_type="办公", reimbursement_status="未报销"),
        Invoice(id=5, invoice_number="INV005", total_amount=250.0, business_type="餐饮", reimbursement_status="未报销"),
        Invoice(id=6, invoice_number="INV006", total_amount=50.0, business_type="交通", reimbursement_status="未报销"),
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


class TestComboService:
    """测试凑票服务"""
    
    def test_find_combinations_basic(self, combo_service, sample_invoices):
        """测试基本凑票功能"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(target_amount=300.0, amount_mode="less")
            solutions = combo_service.find_combinations(params)
            
            assert len(solutions) > 0
            # 应该找到正好 300 的方案 (INV003 或 INV001+INV002)
            exact_solutions = [s for s in solutions if abs(s.difference) < 0.01]
            assert len(exact_solutions) > 0
    
    def test_find_combinations_less_mode(self, combo_service, sample_invoices):
        """测试"可少于"模式"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(target_amount=500.0, amount_mode="less")
            solutions = combo_service.find_combinations(params)
            
            # 所有方案的差额应该 <= 0 (不超过目标)
            for sol in solutions:
                assert sol.difference <= 0.01  # 允许浮点误差
    
    def test_find_combinations_greater_mode(self, combo_service, sample_invoices):
        """测试"可大于"模式"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(target_amount=300.0, amount_mode="greater")
            solutions = combo_service.find_combinations(params)
            
            # 所有方案的差额应该 >= 0 (不小于目标)
            for sol in solutions:
                assert sol.difference >= -0.01  # 允许浮点误差
    
    def test_find_combinations_strategy_fewest(self, combo_service, sample_invoices):
        """测试"张数最少"策略"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(target_amount=300.0, amount_mode="less", strategy="fewest")
            solutions = combo_service.find_combinations(params)
            
            # 第一个方案应该是张数最少的
            if len(solutions) > 1:
                assert solutions[0].count <= solutions[1].count
    
    def test_find_combinations_strategy_most(self, combo_service, sample_invoices):
        """测试"张数最多"策略"""
        with patch.object(combo_service._dao, 'get_all', return_value=sample_invoices):
            params = ComboParams(target_amount=500.0, amount_mode="less", strategy="most")
            solutions = combo_service.find_combinations(params)
            
            # 第一个方案应该是张数最多的
            if len(solutions) > 1:
                assert solutions[0].count >= solutions[1].count
    
    def test_find_combinations_no_invoices(self, combo_service):
        """测试没有发票的情况"""
        with patch.object(combo_service._dao, 'get_all', return_value=[]):
            params = ComboParams(target_amount=300.0)
            solutions = combo_service.find_combinations(params)
            
            assert len(solutions) == 0
    
    def test_find_combinations_filter_business_type(self, combo_service, sample_invoices):
        """测试业务类型过滤"""
        # 只返回餐饮类型的发票
        food_invoices = [inv for inv in sample_invoices if inv.business_type == "餐饮"]
        
        with patch.object(combo_service._dao, 'get_all', return_value=food_invoices):
            params = ComboParams(
                target_amount=350.0,
                business_type="餐饮"
            )
            solutions = combo_service.find_combinations(params)
            
            # 所有方案的发票都应该是餐饮类型
            for sol in solutions:
                for inv in sol.invoices:
                    assert inv.business_type == "餐饮"
    
    def test_set_reimbursement_status(self, combo_service):
        """测试批量设置报销状态"""
        with patch.object(combo_service._dao, 'update_field', return_value=None) as mock_update:
            invoice_ids = [1, 2, 3]
            updated = combo_service.set_reimbursement_status(invoice_ids, "报销中")
            
            assert updated == 3
            assert mock_update.call_count == 3
    
    def test_set_reimbursement_status_invalid(self, combo_service):
        """测试无效的报销状态"""
        with pytest.raises(ValueError):
            combo_service.set_reimbursement_status([1, 2], "无效状态")
    
    def test_greedy_search_large_dataset(self, combo_service):
        """测试大规模数据的贪心搜索"""
        # 创建 60 张发票（超过 50 张触发贪心搜索）
        large_invoices = [
            Invoice(id=i, invoice_number=f"INV{i:03d}", total_amount=10.0 + i, reimbursement_status="未报销")
            for i in range(60)
        ]
        
        with patch.object(combo_service._dao, 'get_all', return_value=large_invoices):
            params = ComboParams(target_amount=500.0, amount_mode="less")
            solutions = combo_service.find_combinations(params)
            
            # 应该返回至少一个方案
            assert len(solutions) > 0


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
