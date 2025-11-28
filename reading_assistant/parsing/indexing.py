from __future__ import annotations

from typing import Iterable, Protocol
from pathlib import Path

from whoosh import index
from whoosh.fields import ID, NUMERIC, TEXT, Schema
from whoosh.qparser import QueryParser

from .models import BlockRecord


class Indexer(Protocol):
    def index_book(self, book_id: str, blocks: Iterable[BlockRecord]) -> None:
        ...


class NoopIndexer:
    """
    Default indexer stub. Keeps the pipeline wired without pulling in Whoosh.
    """

    def index_book(self, book_id: str, blocks: Iterable[BlockRecord]) -> None:
        return None


class WhooshIndexer:
    """
    File-system backed Whoosh indexer. Creates an index if not present and
    re-indexes all blocks for a given book by first deleting existing docs.
    """

    def __init__(self, index_dir: Path):
        self.index_dir = index_dir
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.schema = Schema(
            book_id=ID(stored=True),
            block_id=ID(stored=True, unique=True),
            page_id=ID(stored=True),
            reading_order=NUMERIC(stored=True, sortable=True),
            text=TEXT(stored=True),
        )
        if index.exists_in(self.index_dir):
            self.ix = index.open_dir(self.index_dir)
        else:
            self.ix = index.create_in(self.index_dir, self.schema)

    def index_book(self, book_id: str, blocks: Iterable[BlockRecord]) -> None:
        # Remove old entries for the book to keep indexing idempotent.
        writer = self.ix.writer()
        writer.delete_by_term("book_id", book_id)
        for block in blocks:
            writer.add_document(
                book_id=book_id,
                block_id=block.id,
                page_id=block.page_id,
                reading_order=block.reading_order,
                text=block.text or "",
            )
        writer.commit()

    def delete_book(self, book_id: str) -> None:
        writer = self.ix.writer()
        writer.delete_by_term("book_id", book_id)
        writer.commit()

    def search(self, query_str: str, limit: int = 10):
        """
        Return a list of plain dicts so callers are safe after the searcher closes.
        """
        qp = QueryParser("text", schema=self.schema)
        q = qp.parse(query_str)
        with self.ix.searcher() as searcher:
            results = searcher.search(q, limit=limit)
            hits = []
            for hit in results:
                fields = hit.fields()
                hits.append(
                    {
                        "block_id": fields.get("block_id"),
                        "page_id": fields.get("page_id"),
                        "reading_order": fields.get("reading_order"),
                        "text": fields.get("text"),
                    }
                )
            return hits
