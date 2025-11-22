import json
from datetime import datetime
from pathlib import Path

import pytest

from reading_assistant.parsing import (
    BlockRecord,
    BookRecord,
    BookStatus,
    DummyParsingEngine,
    InMemoryParsingRepository,
    LocalBookStorage,
    NoopIndexer,
    PageRecord,
    ParseJobPhase,
    ParseJobRecord,
    ParseJobState,
    ParsingWorker,
    SectionRecord,
    SqlAlchemyParsingRepository,
    StoragePaths,
    WhooshIndexer,
)
from reading_assistant.parsing.engine import DoclingParsingEngine
from reading_assistant.parsing.models import BBox


def test_sqlalchemy_repository_roundtrip(tmp_path):
    db_path = tmp_path / "test.db"
    repo = SqlAlchemyParsingRepository(f"sqlite+pysqlite:///{db_path}")

    book = BookRecord(
        id="book-1",
        user_id="user-1",
        file_md5="abcd",
        title="Test",
        author=None,
        source="upload",
        original_file_path="input.pdf",
        language="en",
        parse_version="v1",
        status=BookStatus.UPLOADED,
    )
    repo.save_book(book)
    fetched = repo.get_book(book.id)
    assert fetched and fetched.title == "Test"

    job = ParseJobRecord(
        id="job-1",
        book_id=book.id,
        state=ParseJobState.QUEUED,
        phase=ParseJobPhase.PRECHECK,
        current_page=0,
        started_at=datetime.utcnow(),
    )
    repo.save_job(job)
    repo.update_job_state_phase(job.id, state=ParseJobState.RUNNING, current_page=2, total_pages=10, error_message=None)
    updated_job = repo.get_job(job.id)
    assert updated_job and updated_job.state == ParseJobState.RUNNING and updated_job.current_page == 2

    page = PageRecord(
        id="page-1",
        book_id=book.id,
        page_number=1,
        width=612.0,
        height=792.0,
        render_image_path=None,
        thumbnail_image_path=None,
        parse_status="parsed",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    section = SectionRecord(
        id="sec-1",
        book_id=book.id,
        parent_section_id=None,
        level=1,
        title_text="Intro",
        start_page_number=1,
        end_page_number=1,
        order_index=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    block = BlockRecord(
        id="blk-1",
        book_id=book.id,
        page_id=page.id,
        section_id=section.id,
        block_type="paragraph",
        text="Hello",
        markup=None,
        bbox_x=0,
        bbox_y=0,
        bbox_w=10,
        bbox_h=10,
        reading_order=0,
        asset_id=None,
        source_id="src-1",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    repo.upsert_pages([page])
    repo.upsert_sections([section])
    repo.upsert_blocks([block])
    blocks = repo.list_blocks_for_book(book.id)
    assert len(blocks) == 1
    assert blocks[0].text == "Hello"


def test_worker_ingests_dummy_engine(tmp_path):
    storage = LocalBookStorage(StoragePaths(tmp_path / "data"))
    repo = InMemoryParsingRepository()
    engine = DummyParsingEngine()
    indexer = NoopIndexer()
    worker = ParsingWorker(
        repository=repo,
        storage=storage,
        engine=engine,
        indexer=indexer,
        batch_size=10,
        persist_engine_output=True,
    )

    sample_pdf = tmp_path / "sample.txt"
    sample_pdf.write_text("Paragraph one.\n\nParagraph two.", encoding="utf-8")

    book = BookRecord(
        id="book-1",
        user_id="user-1",
        file_md5="abcd",
        title="Dummy",
        author=None,
        source="upload",
        original_file_path=str(sample_pdf),
        language="en",
        parse_version=engine.engine_version,
        status=BookStatus.UPLOADED,
    )
    repo.save_book(book)
    job = ParseJobRecord(
        id="job-1",
        book_id=book.id,
        state=ParseJobState.QUEUED,
        phase=ParseJobPhase.PRECHECK,
        current_page=0,
        started_at=datetime.utcnow(),
    )
    repo.save_job(job)

    worker.run_job(job.id)

    updated_job = repo.get_job(job.id)
    updated_book = repo.get_book(book.id)
    assert updated_job and updated_job.state == ParseJobState.COMPLETED
    assert updated_book and updated_book.status == BookStatus.PARSED
    blocks = repo.list_blocks_for_book(book.id)
    assert len(blocks) == 2
    docling_out = storage.paths.docling_output_path(book.id)
    assert docling_out.exists()


def test_whoosh_indexer(tmp_path):
    index_dir = tmp_path / "whoosh"
    indexer = WhooshIndexer(index_dir)
    blocks = [
        BlockRecord(
            id="blk-1",
            book_id="book-1",
            page_id="page-1",
            section_id=None,
            block_type="paragraph",
            text="The quick brown fox",
            markup=None,
            bbox_x=0,
            bbox_y=0,
            bbox_w=10,
            bbox_h=10,
            reading_order=0,
            asset_id=None,
            source_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        BlockRecord(
            id="blk-2",
            book_id="book-1",
            page_id="page-1",
            section_id=None,
            block_type="paragraph",
            text="jumps over the lazy dog",
            markup=None,
            bbox_x=0,
            bbox_y=0,
            bbox_w=10,
            bbox_h=10,
            reading_order=1,
            asset_id=None,
            source_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    ]
    indexer.index_book("book-1", blocks)
    results = indexer.search("quick")
    assert len(results) == 1
    assert results[0]["block_id"] == "blk-1"


def test_docling_bbox_coercion_variants():
    engine = DoclingParsingEngine.__new__(DoclingParsingEngine)
    bbox_obj = type("BBoxObj", (), {"x": 1, "y": 2, "w": 3, "h": 4})()
    converted = engine._coerce_bbox(bbox_obj)
    assert converted == BBox(1, 2, 3, 4)

    bbox_tuple = (0, 0, 10, 20)
    converted = engine._coerce_bbox(bbox_tuple)
    assert converted == BBox(0, 0, 10, 20)

    bbox_dict_like = type("BBoxLike", (), {"left": 1, "top": 2, "width": 3, "height": 4})()
    converted = engine._coerce_bbox(bbox_dict_like)
    assert converted == BBox(1, 2, 3, 4)

