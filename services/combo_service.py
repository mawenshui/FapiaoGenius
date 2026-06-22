"""智能凑票服务 — 组合优化算法 + 结果排序"""

from typing import Optional
from dataclasses import dataclass, field
from models.invoice import Invoice
from database.invoice_dao import InvoiceDAO, FilterCriteria
from core.logger import logger


# 金额模式中文映射
AMOUNT_MODE_NAMES = {
    "less": "可少于规定金额",
    "greater": "可大于规定金额",
}

# 挑选策略中文映射
STRATEGY_NAMES = {
    "fewest": "张数最少",
    "most": "张数最多",
    "large_first": "大额优先",
    "small_first": "小额优先",
}


@dataclass
class ComboParams:
    """凑票参数"""
    target_amount: float  # 目标金额
    amount_mode: str = "less"  # less: 可少于 | greater: 可大于
    strategy: str = "fewest"  # fewest: 张数最少 | most: 张数最多 | large_first: 大额优先 | small_first: 小额优先
    business_type: Optional[str] = None  # 业务类型过滤
    invoice_type: Optional[str] = None  # 发票类型过滤
    reimbursement_status: Optional[str] = None  # 报销状态过滤
    max_solutions: int = 10  # 最多返回方案数


@dataclass
class ComboSolution:
    """凑票方案"""
    invoices: list[Invoice] = field(default_factory=list)
    total_amount: float = 0.0
    difference: float = 0.0  # 与目标金额的差值 (正数=超出, 负数=不足)
    count: int = 0
    
    def __post_init__(self):
        if self.invoices:
            self.total_amount = sum(inv.total_amount for inv in self.invoices)
            self.count = len(self.invoices)


class ComboService:
    """智能凑票服务"""
    
    def __init__(self):
        self._dao = InvoiceDAO()
    
    def find_combinations(self, params: ComboParams) -> list[ComboSolution]:
        """
        查找最优发票组合
        
        所有策略统一使用回溯搜索找到差额最小的方案集合，
        策略仅影响结果的排序优先级。
        
        策略说明：
        - fewest（张数最少）：优先返回张数少的方案
        - most（张数最多）：优先返回张数多的方案
        - large_first（大额优先）：优先返回平均金额大的方案
        - small_first（小额优先）：优先返回平均金额小的方案
        
        Returns:
            按策略排序的方案列表
        """
        # 记录开始日志
        mode_name = AMOUNT_MODE_NAMES.get(params.amount_mode, params.amount_mode)
        strategy_name = STRATEGY_NAMES.get(params.strategy, params.strategy)
        logger.info(f"[凑票] ===== 开始凑票计算 =====")
        logger.info(f"[凑票] 参数: 目标金额=¥{params.target_amount:.2f}, 金额模式={mode_name}, 挑选策略={strategy_name}")
        logger.info(f"[凑票] 过滤条件: 业务类型={params.business_type or '全部'}, 发票类型={params.invoice_type or '全部'}, 报销状态={params.reimbursement_status or '未报销'}")
        logger.info(f"[凑票] 最大返回方案数: {params.max_solutions}")
        
        # 1. 获取符合条件的发票
        invoices = self._get_eligible_invoices(params)
        
        if not invoices:
            logger.warning("[凑票] 没有符合条件的发票参与凑票，计算终止")
            return []
        
        total_invoice_amount = sum(inv.total_amount for inv in invoices)
        logger.info(f"[凑票] 符合条件的发票: {len(invoices)} 张, 总金额=¥{total_invoice_amount:.2f}")
        logger.debug(f"[凑票] 发票金额明细: {[f'{inv.invoice_number}:¥{inv.total_amount:.2f}' for inv in invoices[:10]]}{'...' if len(invoices) > 10 else ''}")
        
        # 2. 统一使用回溯搜索（所有模式内置差额最小逻辑）
        logger.info(f"[凑票] 使用「{strategy_name}」策略搜索方案")
        solutions = self._backtrack_search(invoices, params)
        
        if not solutions:
            logger.warning(f"[凑票] 搜索完成，未找到任何符合条件的方案")
            return []
        
        logger.info(f"[凑票] 搜索完成，找到 {len(solutions)} 个方案")
        
        # 3. 按策略排序
        solutions = self._sort_by_strategy(solutions, params)
        
        # 4. 限制返回数量
        original_count = len(solutions)
        solutions = solutions[:params.max_solutions]
        if len(solutions) < original_count:
            logger.info(f"[凑票] 截取前 {len(solutions)} 个方案（原有 {original_count} 个）")
        
        # 记录最终结果
        logger.info(f"[凑票] ===== 凑票计算完成 =====")
        logger.info(f"[凑票] 最终返回 {len(solutions)} 个方案")
        for i, sol in enumerate(solutions[:3], 1):  # 只记录前3个方案的详情
            inv_numbers = [inv.invoice_number for inv in sol.invoices[:5]]
            logger.info(f"[凑票] 方案{i}: {sol.count}张, 合计=¥{sol.total_amount:.2f}, 差额=¥{sol.difference:+.2f}, 发票={inv_numbers}{'...' if len(sol.invoices) > 5 else ''}")
        if len(solutions) > 3:
            logger.info(f"[凑票] ... 还有 {len(solutions) - 3} 个方案未详细记录")
        
        return solutions
    
    def _get_eligible_invoices(self, params: ComboParams) -> list[Invoice]:
        """获取符合条件的发票"""
        criteria = FilterCriteria(
            business_type=params.business_type,
            invoice_type=params.invoice_type,
            reimbursement_status=params.reimbursement_status,
        )
        
        # 只获取"未报销"状态的发票（如果未指定状态过滤）
        if not params.reimbursement_status:
            criteria.reimbursement_status = "未报销"
        
        return self._dao.get_all(criteria)
    
    def _backtrack_search(self, invoices: list[Invoice], params: ComboParams) -> list[ComboSolution]:
        """
        回溯搜索引擎：搜索所有符合金额模式的方案，优先保留差额最小的
        
        这是统一的搜索引擎，所有策略都通过此方法搜索方案。
        策略仅影响搜索完成后的排序（由 _sort_by_strategy 处理）。
        """
        import heapq
        
        target = params.target_amount
        
        # 智能差额阈值：目标金额的 15% 或 2000 元，取较大值
        diff_threshold = max(target * 0.15, 2000.0)
        logger.info(f"[凑票] 回溯搜索: 智能差额阈值=±¥{diff_threshold:.2f}")
        
        if len(invoices) > 50:
            # 大规模数据：贪心近似
            logger.info(f"[凑票] 发票数量 {len(invoices)} 张 > 50，采用贪心近似搜索")
            return self._greedy_search(invoices, params)
        
        logger.info(f"[凑票] 发票数量 {len(invoices)} 张 ≤ 50，采用智能回溯搜索")
        
        # 按金额降序排序（优化剪枝效率）
        invoices_sorted = sorted(invoices, key=lambda x: x.total_amount, reverse=True)
        
        # 使用优先队列（堆）保留最优方案
        # 堆中存储 (abs(difference), counter, solution)，counter 用于保证唯一性
        best_solutions_heap = []
        solution_counter = [0]  # 使用列表以便在嵌套函数中修改
        max_heap_size = params.max_solutions * 20  # 保留足够多的候选
        max_nodes = 500000
        nodes_visited = [0]
        
        logger.debug(f"[凑票] 搜索参数: 目标=¥{target:.2f}, 阈值=±¥{diff_threshold:.2f}, 最大节点={max_nodes}")
        
        current_combo = []
        current_sum = 0.0
        
        def backtrack(start_idx: int) -> bool:
            """返回 True 表示应该停止搜索"""
            nonlocal current_sum
            nodes_visited[0] += 1
            
            # 检查是否达到搜索限制
            if nodes_visited[0] > max_nodes:
                logger.debug(f"[凑票] 达到最大节点数限制 {max_nodes}，停止搜索")
                return True
            
            # 智能剪枝：根据金额模式剪枝
            if params.amount_mode == "less":
                # less 模式：超过目标就剪枝
                if current_sum > target:
                    return False
            elif params.amount_mode == "greater":
                # greater 模式：超过目标+阈值就剪枝（再加发票只会更大）
                if current_sum > target + diff_threshold:
                    return False
            
            # 检查当前组合是否符合条件
            if current_combo:
                diff = current_sum - target
                abs_diff = abs(diff)
                
                # 根据金额模式判断是否有效
                is_valid = False
                if params.amount_mode == "less":
                    is_valid = diff <= 0 and abs_diff <= diff_threshold
                elif params.amount_mode == "greater":
                    is_valid = diff >= 0 and abs_diff <= diff_threshold
                
                if is_valid:
                    solution = ComboSolution(
                        invoices=list(current_combo),
                        total_amount=current_sum,
                        difference=diff
                    )
                    
                    # 使用堆保留最优方案（差额最小的）
                    # 使用 counter 保证唯一性，避免比较 ComboSolution 对象
                    if len(best_solutions_heap) < max_heap_size:
                        heapq.heappush(best_solutions_heap, (-abs_diff, solution_counter[0], solution))
                        solution_counter[0] += 1
                    elif abs_diff < -best_solutions_heap[0][0]:
                        # 当前方案比堆中最差的更好，替换
                        heapq.heappop(best_solutions_heap)
                        heapq.heappush(best_solutions_heap, (-abs_diff, solution_counter[0], solution))
                        solution_counter[0] += 1
            
            # 对于 greater 模式，当前和已满足条件时，记录方案后无需继续添加更多发票
            # （继续添加只会让差额更大，不会产生更优方案）
            if current_combo and params.amount_mode == "greater" and current_sum >= target and (current_sum - target) <= diff_threshold:
                # 已记录当前方案，跳过继续添加（剪枝子树）
                return False
            
            # 继续搜索
            for i in range(start_idx, len(invoices_sorted)):
                if nodes_visited[0] > max_nodes:
                    return True
                
                inv = invoices_sorted[i]
                current_combo.append(inv)
                current_sum += inv.total_amount
                
                should_stop = backtrack(i + 1)
                
                current_combo.pop()
                current_sum -= inv.total_amount
                
                if should_stop:
                    return True
            
            return False
        
        backtrack(0)
        
        # 从堆中提取所有方案
        solutions = [sol for _, _, sol in best_solutions_heap]
        
        # 按差额绝对值升序排序（后续由 _sort_by_strategy 按策略重排）
        solutions.sort(key=lambda s: abs(s.difference))
        
        logger.info(f"[凑票] 智能回溯完成: 访问 {nodes_visited[0]} 个节点, 保留 {len(solutions)} 个优质方案")
        if nodes_visited[0] >= max_nodes:
            logger.warning(f"[凑票] 搜索因达到节点数限制而提前终止")
        
        if solutions:
            best_diff = min(abs(sol.difference) for sol in solutions)
            worst_diff = max(abs(sol.difference) for sol in solutions)
            logger.info(f"[凑票] 方案质量: 最优差额=¥{best_diff:.2f}, 最差差额=¥{worst_diff:.2f}")
        
        return solutions
    
    def _greedy_search(self, invoices: list[Invoice], params: ComboParams) -> list[ComboSolution]:
        """
        智能贪心近似搜索（适用于大规模数据 >50 张发票）
        
        按金额排序后贪心选择，应用智能差额阈值过滤不合理方案。
        """
        target = params.target_amount
        
        # 智能差额阈值：与回溯搜索保持一致
        diff_threshold = max(target * 0.15, 2000.0)
        logger.info(f"[凑票] 开始智能贪心搜索，目标=¥{target:.2f}, 阈值=±¥{diff_threshold:.2f}")
        
        solutions = []
        
        # 策略1: 大额优先贪心（按金额降序）
        logger.debug(f"[凑票] 贪心策略1: 大额优先（按金额降序选择）")
        combo = []
        current_sum = 0.0
        for inv in invoices:
            # less 模式：不能超过目标
            if params.amount_mode == "less" and current_sum + inv.total_amount > target:
                continue
            combo.append(inv)
            current_sum += inv.total_amount
            # greater 模式：达到目标就停止
            if params.amount_mode == "greater" and current_sum >= target:
                break
        
        if combo:
            diff = current_sum - target
            abs_diff = abs(diff)
            # 检查是否在阈值范围内且符合金额模式
            is_valid = False
            if params.amount_mode == "less":
                is_valid = diff <= 0 and abs_diff <= diff_threshold
            elif params.amount_mode == "greater":
                is_valid = diff >= 0 and abs_diff <= diff_threshold
            if is_valid:
                logger.debug(f"[凑票] 贪心策略1结果: {len(combo)}张, 合计=¥{current_sum:.2f}, 差额=¥{diff:+.2f} ✓")
                solutions.append(ComboSolution(
                    invoices=combo,
                    total_amount=current_sum,
                    difference=diff
                ))
            else:
                logger.debug(f"[凑票] 贪心策略1结果: 差额¥{diff:+.2f} 不符合模式要求，已过滤")
        else:
            logger.debug(f"[凑票] 贪心策略1未找到有效组合")
        
        # 策略2: 小额优先贪心（按金额升序）
        logger.debug(f"[凑票] 贪心策略2: 小额优先（按金额升序选择）")
        combo = []
        current_sum = 0.0
        for inv in reversed(invoices):
            # less 模式：不能超过目标
            if params.amount_mode == "less" and current_sum + inv.total_amount > target:
                continue
            combo.append(inv)
            current_sum += inv.total_amount
            # greater 模式：达到目标就停止
            if params.amount_mode == "greater" and current_sum >= target:
                break
        
        if combo:
            diff = current_sum - target
            abs_diff = abs(diff)
            # 检查是否在阈值范围内且符合金额模式
            is_valid = False
            if params.amount_mode == "less":
                is_valid = diff <= 0 and abs_diff <= diff_threshold
            elif params.amount_mode == "greater":
                is_valid = diff >= 0 and abs_diff <= diff_threshold
            if is_valid:
                logger.debug(f"[凑票] 贪心策略2结果: {len(combo)}张, 合计=¥{current_sum:.2f}, 差额=¥{diff:+.2f} ✓")
                solutions.append(ComboSolution(
                    invoices=combo,
                    total_amount=current_sum,
                    difference=diff
                ))
            else:
                logger.debug(f"[凑票] 贪心策略2结果: 差额¥{diff:+.2f} 不符合模式要求，已过滤")
        else:
            logger.debug(f"[凑票] 贪心策略2未找到有效组合")
        
        logger.info(f"[凑票] 贪心搜索完成，保留 {len(solutions)} 个优质方案")
        return solutions
    
    def _sort_by_strategy(self, solutions: list[ComboSolution], params: ComboParams) -> list[ComboSolution]:
        """按挑选策略排序（所有方案已通过回溯搜索找到，此处仅按策略偏好排序）"""
        strategy = params.strategy
        strategy_name = STRATEGY_NAMES.get(strategy, strategy)
        logger.debug(f"[凑票] 开始按「{strategy_name}」策略对 {len(solutions)} 个方案排序")
        
        if strategy == "fewest":
            # 张数最少优先，张数相同则差额绝对值小优先
            solutions.sort(key=lambda s: (s.count, abs(s.difference)))
            logger.debug(f"[凑票] 排序规则: 张数升序 → 差额绝对值升序")
        elif strategy == "most":
            # 张数最多优先
            solutions.sort(key=lambda s: (-s.count, abs(s.difference)))
            logger.debug(f"[凑票] 排序规则: 张数降序 → 差额绝对值升序")
        elif strategy == "large_first":
            # 大额优先（平均金额大优先）
            solutions.sort(key=lambda s: (-s.total_amount / s.count if s.count > 0 else 0, abs(s.difference)))
            logger.debug(f"[凑票] 排序规则: 平均金额降序 → 差额绝对值升序")
        elif strategy == "small_first":
            # 小额优先（平均金额小优先）
            solutions.sort(key=lambda s: (s.total_amount / s.count if s.count > 0 else 0, abs(s.difference)))
            logger.debug(f"[凑票] 排序规则: 平均金额升序 → 差额绝对值升序")
        
        if solutions:
            best = solutions[0]
            logger.debug(f"[凑票] 排序完成，最优方案: {best.count}张, 合计=¥{best.total_amount:.2f}, 差额=¥{best.difference:+.2f}")
        
        return solutions
    
    def set_reimbursement_status(self, invoice_ids: list[int], status: str) -> int:
        """
        批量设置报销状态
        
        Args:
            invoice_ids: 发票 ID 列表
            status: "报销中" 或 "已报销"
        
        Returns:
            成功更新的记录数
        """
        if status not in ("报销中", "已报销"):
            raise ValueError(f"无效的报销状态: {status}")
        
        updated = 0
        for inv_id in invoice_ids:
            try:
                self._dao.update_field(inv_id, 'reimbursement_status', status)
                updated += 1
            except Exception as e:
                logger.error(f"更新发票 {inv_id} 状态失败: {e}")
        
        logger.info(f"批量更新报销状态: {updated}/{len(invoice_ids)} 成功, 状态={status}")
        return updated


# 全局服务实例
combo_service = ComboService()
