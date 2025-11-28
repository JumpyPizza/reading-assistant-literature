from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path

from reading_assistant.parsing import (
    DoclingParsingEngine,
    LocalBookStorage,
    ParsingRepository,
    ParsingWorker,
    SqlAlchemyParsingRepository,
    StoragePaths,
    WhooshIndexer,
)


@lru_cache(maxsize=1)
def get_repo() -> ParsingRepository:
    db_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./data/reading_assistant.db")
    return SqlAlchemyParsingRepository(db_url)


@lru_cache(maxsize=1)
def get_storage() -> LocalBookStorage:
    root = Path(os.getenv("BOOK_STORAGE_ROOT", "./data"))
    return LocalBookStorage(StoragePaths(root))


@lru_cache(maxsize=1)
def get_indexer() -> WhooshIndexer:
    whoosh_dir = Path(os.getenv("WHOOSH_DIR", "./data/whoosh"))
    return WhooshIndexer(whoosh_dir)


def build_worker(perform_ocr: bool) -> ParsingWorker:
    storage = get_storage()
    indexer = get_indexer()
    db_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./data/reading_assistant.db")
    batch_size = int(os.getenv("WORKER_BATCH_SIZE", "25"))
    engine_version = os.getenv("ENGINE_VERSION", "docling-latest")

    repo = SqlAlchemyParsingRepository(db_url)
    engine = DoclingParsingEngine(perform_ocr=perform_ocr, engine_version=engine_version)
    return ParsingWorker(
        repository=repo,
        storage=storage,
        engine=engine,
        indexer=indexer,
        batch_size=batch_size,
        persist_engine_output=True,
        render_page_previews=True,
    )


def build_book_id(title: str) -> str:
    normalized = title.strip().lower()
    slug = "".join(ch if ch.isalnum() else "-" for ch in normalized).strip("-") or "book"
    digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


def compute_md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()
