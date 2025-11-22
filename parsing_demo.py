"""
Minimal runnable example of the parsing pipeline using the dummy engine.

This script keeps everything in-memory and writes derived assets/docling output
to ./data/books/{book_id}/ for inspection.
"""

from pathlib import Path
from datetime import datetime

from reading_assistant.parsing import (
    BookRecord,
    BookStatus,
    DummyParsingEngine,
    InMemoryParsingRepository,
    LocalBookStorage,
    NoopIndexer,
    ParseJobPhase,
    ParseJobRecord,
    ParseJobState,
    ParsingWorker,
    StoragePaths,
)


def main() -> None:
    repo = InMemoryParsingRepository()
    storage = LocalBookStorage(StoragePaths(Path("./data")))
    engine = DummyParsingEngine()
    indexer = NoopIndexer()
    worker = ParsingWorker(
        repository=repo,
        storage=storage,
        engine=engine,
        indexer=indexer,
        batch_size=10,
        persist_engine_output=False,
    )

    book_id = "book-local"
    job_id = "job-local"
    sample_pdf_path = Path("sample_book.txt")

    book = BookRecord(
        id=book_id,
        user_id="local-user",
        file_md5="deadbeef" * 4,
        title="Sample Book",
        author="Local Author",
        source="upload",
        original_file_path=str(sample_pdf_path),
        language="en",
        parse_version=engine.engine_version,
        status=BookStatus.UPLOADED,
    )
    repo.save_book(book)

    job = ParseJobRecord(
        id=job_id,
        book_id=book_id,
        state=ParseJobState.QUEUED,
        phase=ParseJobPhase.PRECHECK,
        current_page=0,
        started_at=datetime.utcnow(),
    )
    repo.save_job(job)

    worker.run_job(job_id)

    print(f"Job {job_id} state: {repo.get_job(job_id).state}")
    for block in repo.list_blocks_for_book(book_id):
        print(f"[page {block.page_id}] {block.text}")


if __name__ == "__main__":
    main()
