"""Request replicas must not repeat shared-resource bootstrap writes."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

from cygnusx import main
from cygnusx.core.config import get_settings

pytestmark = pytest.mark.unit


async def test_replica_starts_without_shared_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings().model_copy(
        update={
            "web_bootstrap_enabled": False,
            "knowledge_auto_reindex_enabled": True,
            "welcome_enabled": True,
            "dynamic_model_routing_enabled": False,
        }
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "setup_logging", MagicMock())
    monkeypatch.setattr("cygnusx.core.telemetry.setup_telemetry", MagicMock())
    monkeypatch.setattr(main, "_validate_memory_embedding_provider", AsyncMock())
    init_db, close_db = AsyncMock(), AsyncMock()
    monkeypatch.setattr("cygnusx.infrastructure.database.session.init_db", init_db)
    monkeypatch.setattr("cygnusx.infrastructure.database.session.close_db", close_db)
    factory = MagicMock(side_effect=AssertionError("Replica bootstrap must not open a session"))
    sandbox = MagicMock(side_effect=AssertionError("Replica must not adopt shared warm sandboxes"))
    monkeypatch.setattr("cygnusx.infrastructure.database.session.get_session_factory", factory)
    monkeypatch.setattr("cygnusx.infrastructure.sandbox.get_sandbox_pool", sandbox)
    monkeypatch.setattr(
        "cygnusx.application.services.biothings_service.close_biothings_clients", AsyncMock()
    )
    monkeypatch.setattr(
        "cygnusx.application.services.research_data_service.close_research_clients", AsyncMock()
    )
    enqueue = MagicMock()
    monkeypatch.setattr("cygnusx.infrastructure.celery_app.tasks.welcome.reconcile.apply_async", enqueue)

    async with main.lifespan(FastAPI()):
        await asyncio.sleep(0)
        init_db.assert_awaited_once()
        factory.assert_not_called()
        sandbox.assert_not_called()
        enqueue.assert_not_called()
    await asyncio.sleep(0)
    close_db.assert_awaited_once()
