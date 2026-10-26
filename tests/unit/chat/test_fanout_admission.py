"""FanoutAdmission 单轮准入语义测试。

对应验收矩阵（docs/info/26.10.26 方案 §6）：
- T01 超上限校验拒绝不占 accepted 配额；
- T02 校验拒绝后同轮合法修正可放行；
- T04 accepted 后同轮第二个 fan-out 受控拒绝；
- 统一路由预执行后模型侧不得双派；
- 校验尝试预算封顶，防止同轮无限修正重试。
"""

from __future__ import annotations

from cygnusx.application.services.chat.fanout_admission import FanoutAdmission


def test_validation_rejection_does_not_consume_accepted_quota() -> None:
    admission = FanoutAdmission(max_accepted_per_round=1)

    assert admission.check_preexecuted() is None
    assert admission.begin_validation() is None
    # 校验失败（如 5 > max_parallel=4）：不计数
    admission.mark_rejected()

    # 同轮修正为合法参数后可正常放行（T02）
    assert admission.begin_validation() is None
    assert admission.try_commit() is None
    assert admission.accepted_count == 1


def test_second_dispatch_rejected_after_commit() -> None:
    admission = FanoutAdmission(max_accepted_per_round=1)

    assert admission.begin_validation() is None
    assert admission.try_commit() is None
    # T04：已成功 accepted 的同轮第二个 fan-out 必须拒绝
    assert admission.begin_validation() is None
    assert admission.try_commit() is not None


def test_validation_attempt_budget_caps_retries() -> None:
    admission = FanoutAdmission(max_accepted_per_round=1, max_validation_attempts=2)

    assert admission.begin_validation() is None
    admission.mark_rejected()
    assert admission.begin_validation() is None
    admission.mark_rejected()
    # 第三次校验尝试超出预算，直接拒绝（调用方在此中断，不再进入 commit）
    assert admission.begin_validation() is not None


def test_preexecuted_blocks_model_initiated_dispatch() -> None:
    admission = FanoutAdmission(max_accepted_per_round=1)
    admission.mark_preexecuted()

    assert admission.check_preexecuted() is not None
    # 预执行已占额度，commit 同样拒绝（双保险）
    assert admission.try_commit() is not None


def test_multi_accepted_budget() -> None:
    admission = FanoutAdmission(max_accepted_per_round=2)

    assert admission.try_commit() is None
    assert admission.try_commit() is None
    assert admission.try_commit() is not None
