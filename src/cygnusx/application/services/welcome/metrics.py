"""Welcome operational measurements, with no account-level metric labels."""

from cygnusx.core.telemetry import get_meter

_meter = get_meter("cygnusx.welcome")
generation_runs = _meter.create_counter("welcome_generation_runs_total")
valid_messages = _meter.create_histogram("welcome_batch_valid_messages")
claim_latency = _meter.create_histogram("welcome_claim_latency_ms", unit="ms")
fallbacks = _meter.create_counter("welcome_fallback_total")
impressions = _meter.create_counter("welcome_impressions_total")
llm_tokens = _meter.create_counter("welcome_llm_tokens_total")
pool_age = _meter.create_histogram("welcome_pool_age_days", unit="d")
