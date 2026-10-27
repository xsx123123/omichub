from datetime import datetime
from unittest.mock import MagicMock

from cygnusx.application.services.ai_metrics_service import AiMetricsService


def test_daily_cost_alert_is_deduplicated_for_the_current_calendar_day():
    service = AiMetricsService(MagicMock())
    now = datetime(2026, 8, 3, 16, 30, 0)

    assert service._alert_cooldown_since("daily_cost", now) == datetime(2026, 8, 3)


def test_operational_alerts_keep_the_configured_short_cooldown():
    service = AiMetricsService(MagicMock())
    service._settings = service._settings.model_copy(
        update={"ai_alert_cooldown_minutes": 30}
    )
    now = datetime(2026, 8, 3, 16, 30, 0)

    assert service._alert_cooldown_since("error_rate", now) == datetime(2026, 8, 3, 16)
    assert service._alert_cooldown_since("p95_latency", now) == datetime(2026, 8, 3, 16)


def test_cache_hit_ratio_is_cached_over_prompt_with_bounds():
    service = AiMetricsService(MagicMock())

    assert service._cache_hit_ratio(800, 1000) == 0.8
    assert service._cache_hit_ratio(0, 1000) == 0.0
    assert service._cache_hit_ratio(0, 0) == 0.0
    assert service._cache_hit_ratio(-5, 1000) == 0.0
    # 部分 provider 的 cached 可能因统计口径超过 prompt，截断到 1
    assert service._cache_hit_ratio(1200, 1000) == 1.0


def test_record_ai_call_captures_cached_tokens_into_buffer_row():
    from cygnusx.core import ai_metrics

    ai_metrics._buffer.clear()
    try:
        ai_metrics.record_ai_call(
            "deepseek",
            "deepseek-chat",
            "success",
            123.0,
            {
                "prompt_tokens": 29189,
                "completion_tokens": 500,
                "total_tokens": 29689,
                "cached_tokens": 25000,
            },
            "session-1",
        )
        row = ai_metrics._buffer[-1]
        assert row["cached_tokens"] == 25000
        assert row["prompt_tokens"] == 29189
    finally:
        ai_metrics._buffer.clear()
