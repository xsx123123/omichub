"""Atomic, symlink-resistant local publication; generic backend for object storage."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from cygnusx.application.services.report_snapshot_manifest import (
    open_evidence_file,
    pinned_directory,
)
from cygnusx.core.exceptions import BusinessError, NotFoundError
from cygnusx.infrastructure.storage.backend import StorageBackend
from cygnusx.infrastructure.storage.path_factory import StoragePathFactory


def read_local_archive(path: Path, limit: int | None = None) -> bytes:
    with open_evidence_file(path) as stream:
        return stream.read(-1 if limit is None else limit)


def _atomic_local_write(path: Path, content: bytes) -> None:
    temp = f".{path.name}.{uuid4().hex}.publishing"
    with pinned_directory(path.parent) as directory_fd:
        fd = os.open(
            temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd
        )
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                stream.write(content)
                stream.flush()
                os.fsync(fd)
            os.replace(temp, path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            os.fsync(directory_fd)
        finally:
            os.close(fd)
            with suppress(FileNotFoundError):
                os.unlink(temp, dir_fd=directory_fd)


async def read_archive(
    backend: StorageBackend, factory: StoragePathFactory, relative: str, *, limit: int | None = None
) -> bytes:
    if backend.name == "local":
        return await asyncio.to_thread(read_local_archive, factory.data_root / relative, limit)
    try:
        if limit is not None:
            return await backend.read(relative, limit=limit)
        return await backend.read(relative)
    except (BusinessError, NotFoundError) as exc:
        raise OSError("Archive storage read unavailable") from exc


async def publish_archive(
    backend: StorageBackend,
    factory: StoragePathFactory,
    relative: str,
    content: bytes,
) -> None:
    if backend.name == "local":
        await asyncio.to_thread(_atomic_local_write, factory.data_root / relative, content)
    else:

        async def chunks() -> AsyncIterator[bytes]:
            yield content

        try:
            await backend.write_stream(relative, chunks())
        except BusinessError as exc:
            raise OSError("Archive storage publication unavailable") from exc
