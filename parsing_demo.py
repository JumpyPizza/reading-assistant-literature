"""
Example: run the full parsing pipeline on a real PDF using Docling + SQLite + Whoosh.

Usage:
    python3 parsing_demo.py --pdf /path/to/book.pdf --title "My Book" --book-id book-1
"""

import argparse
import hashlib
from datetime import datetime
from pathlib import Path

from reading_assistant.parsing import (
    BookRecord,
    BookStatus,
    DoclingParsingEngine,
    ParseJobPhase,
    ParseJobRecord,
    ParseJobState,
    ParsingWorker,
    StoragePaths,
    WhooshIndexer,
    SqlAlchemyParsingRepository,
    LocalBookStorage,
)


def compute_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path, help="Path to input PDF")
    parser.add_argument("--title", required=True, help="Book title")
    parser.add_argument("--author", default=None, help="Book author")
    parser.add_argument("--book-id", default="book-demo", help="Book id (for DB/paths)")
    parser.add_argument("--db", default=Path("./data/reading_assistant.db"), type=Path, help="SQLite DB path")
    parser.add_argument("--storage-root", default=Path("./data"), type=Path, help="Storage root for books/assets")
    parser.add_argument("--whoosh-dir", default=Path("./data/whoosh"), type=Path, help="Whoosh index directory")
    parser.add_argument("--language", default="en", help="Language code hint")
    parser.add_argument("--perform-ocr", action="store_true", help="Enable OCR")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise FileNotFoundError(f"PDF not found: {args.pdf}")

    storage = LocalBookStorage(StoragePaths(args.storage_root))
    storage.ensure_base_dirs(args.book_id)
    original_pdf_path = storage.save_original_pdf(args.book_id, args.pdf)

    repo = SqlAlchemyParsingRepository(f"sqlite+pysqlite:///{args.db}")
    indexer = WhooshIndexer(args.whoosh_dir)
    engine = DoclingParsingEngine(perform_ocr=args.perform_ocr)
    worker = ParsingWorker(
        repository=repo,
        storage=storage,
        engine=engine,
        indexer=indexer,
        batch_size=25,
        persist_engine_output=True,
    )

    book = BookRecord(
        id=args.book_id,
        user_id="local-user",
        file_md5=compute_md5(args.pdf),
        title=args.title,
        author=args.author,
        source="upload",
        original_file_path=str(original_pdf_path),
        language=args.language,
        parse_version=engine.engine_version,
        status=BookStatus.UPLOADED,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    repo.save_book(book)

    job_id = f"job-{args.book_id}"
    job = ParseJobRecord(
        id=job_id,
        book_id=args.book_id,
        state=ParseJobState.QUEUED,
        phase=ParseJobPhase.PRECHECK,
        current_page=0,
        started_at=datetime.utcnow(),
    )
    repo.save_job(job)

    print(f"Starting parse job {job_id} for {args.pdf}")
    worker.run_job(job_id)
    final_job = repo.get_job(job_id)
    print(f"Job finished with state={final_job.state}, error={final_job.error_message}")
    print(f"Indexed blocks located in Whoosh dir: {args.whoosh_dir}")


if __name__ == "__main__":
    main()
