"""对话内 fan-out 的单轮准入协调器。

设计要点（对应 CygnusX_multi_agent_fanout.md §9.9 修复记录）：
- validate 先于 reserve：校验拒绝不占 accepted 配额、不产生执行副作用；
- 校验尝试有独立预算（防止模型在同一轮内无限修正重试）；
- 统一意图路由预执行与模型工具调用共用同一准入实例，杜绝同轮双派。

本类纯同步、无 IO，Legacy 与 LangGraph 两条执行路径共用同一份语义。
"""

from __future__ import annotations


class FanoutAdmission:
    """单轮（一次父工具回合）fan-out 准入判定。"""

    def __init__(self, *, max_accepted_per_round: int, max_validation_attempts: int = 2) -> None:
        self._max_accepted = max(1, max_accepted_per_round)
        self._max_validation_attempts = max(1, max_validation_attempts)
        self._accepted = 0
        self._validation_attempts = 0
        self._preexecuted = False

    def mark_preexecuted(self) -> None:
        """统一意图路由已在本轮预执行过一次 fan-out。"""
        self._preexecuted = True
        self._accepted += 1

    def check_preexecuted(self) -> str | None:
        """路由预执行占用本轮额度后，模型侧再次调用一律拒绝。"""
        if self._preexecuted:
            return "本轮统一路由已完成并行分派并注入汇总，请直接基于结果作答，不要重复分派"
        return None

    def begin_validation(self) -> str | None:
        """登记一次校验尝试；超过预算则拒绝（不再允许本轮继续修正）。"""
        if self._validation_attempts >= self._max_validation_attempts:
            return (
                "本轮子 Agent 分派参数连续未通过校验，请检查任务数量、目标 Agent "
                "与子任务描述后再决定下一步"
            )
        self._validation_attempts += 1
        return None

    def mark_rejected(self) -> None:
        """校验拒绝：不占 accepted 配额，同轮仍可在预算内修正重试。"""

    def try_commit(self) -> str | None:
        """校验通过、即将真实分派；超过 accepted 上限则拒绝。"""
        if self._accepted >= self._max_accepted:
            return "本轮已执行过子 Agent 并行分派，请先消化汇总结果再决定下一步"
        self._accepted += 1
        return None

    @property
    def accepted_count(self) -> int:
        return self._accepted
