from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from reading_assistant.parsing import (
    LocalBookStorage,
    BookRecord,
    BookStatus,
    DoclingParsingEngine,
    ParseJobPhase,
    ParseJobRecord,
    ParseJobState,
    ParsingWorker,
    ParsingRepository,
    SqlAlchemyParsingRepository,
    StoragePaths,
    WhooshIndexer,
)


def make_repo() -> ParsingRepository:
    db_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./data/reading_assistant.db")
    return SqlAlchemyParsingRepository(db_url)


def make_storage() -> LocalBookStorage:
    root = Path(os.getenv("BOOK_STORAGE_ROOT", "./data"))
    return LocalBookStorage(StoragePaths(root))


repo = make_repo()
storage = make_storage()

app = FastAPI(title="Reading Assistant API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_page(book_id: str, page_number: int):
    page = repo.get_page(book_id, page_number)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page not found: {book_id} page {page_number}")
    return page


def _build_book_id(title: str) -> str:
    normalized = title.strip().lower()
    slug = "".join(ch if ch.isalnum() else "-" for ch in normalized).strip("-")
    if not slug:
        slug = "book"
    digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


def _compute_md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _make_worker(perform_ocr: bool) -> ParsingWorker:
    database_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./data/reading_assistant.db")
    storage_root = Path(os.getenv("BOOK_STORAGE_ROOT", "./data"))
    whoosh_dir = Path(os.getenv("WHOOSH_DIR", "./data/whoosh"))
    batch_size = int(os.getenv("WORKER_BATCH_SIZE", "25"))
    engine_version = os.getenv("ENGINE_VERSION", "docling-latest")

    repo_local = SqlAlchemyParsingRepository(database_url)
    storage_local = LocalBookStorage(StoragePaths(storage_root))
    indexer = WhooshIndexer(whoosh_dir)
    engine = DoclingParsingEngine(perform_ocr=perform_ocr, engine_version=engine_version)
    return ParsingWorker(
        repository=repo_local,
        storage=storage_local,
        engine=engine,
        indexer=indexer,
        batch_size=batch_size,
        persist_engine_output=True,
        render_page_previews=True,
    )


def _run_job(job_id: str, perform_ocr: bool) -> None:
    worker = _make_worker(perform_ocr)
    worker.run_job(job_id)


@app.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    author: Optional[str] = Form(None),
    language: str = Form("en"),
    perform_ocr: bool = Form(False),
):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    book_id = _build_book_id(title)
    if repo.get_book(book_id):
        raise HTTPException(status_code=409, detail=f"Book already exists: {book_id}")

    tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=".pdf")
    tmp_path = Path(tmp_path_str)
    with os.fdopen(tmp_fd, "wb") as tmp_file:
        tmp_file.write(payload)

    # Save to storage and create records
    storage.ensure_base_dirs(book_id)
    original_pdf_path = storage.save_original_pdf(book_id, tmp_path)
    tmp_path.unlink(missing_ok=True)

    engine = DoclingParsingEngine(perform_ocr=perform_ocr)
    book = BookRecord(
        id=book_id,
        user_id="upload-user",
        file_md5=_compute_md5_bytes(payload),
        title=title,
        author=author,
        source="upload",
        original_file_path=str(original_pdf_path),
        language=language,
        parse_version=engine.engine_version,
        status=BookStatus.UPLOADED,
    )
    repo.save_book(book)

    job_id = f"job-{book_id}"
    job = ParseJobRecord(
        id=job_id,
        book_id=book_id,
        state=ParseJobState.QUEUED,
        phase=ParseJobPhase.PRECHECK,
        current_page=0,
    )
    repo.save_job(job)

    background_tasks.add_task(_run_job, job_id, perform_ocr)
    return {"book_id": book_id, "job_id": job_id}


@app.get("/documents/{book_id}/pages/{page_number}/parsed")
def get_parsed_page(book_id: str, page_number: int):
    page = _get_page(book_id, page_number)
    try:
        blocks = repo.list_blocks_for_page(book_id, page_number)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not blocks:
        raise HTTPException(status_code=404, detail=f"No blocks found for {book_id} page {page_number}")

    return {
        "page": page_number,
        "width": page.width,
        "height": page.height,
        "blocks": [
            {
                "id": blk.id,
                "block_type": blk.block_type,
                "reading_order": blk.reading_order,
                "text": blk.text,
                "bbox": [blk.bbox_x, blk.bbox_y, blk.bbox_w, blk.bbox_h],
                "section_id": blk.section_id,
                "asset_id": blk.asset_id,
            }
            for blk in blocks
        ],
    }


@app.get("/documents/{book_id}/pages/{page_number}/image")
def get_page_image(book_id: str, page_number: int):
    page = _get_page(book_id, page_number)
    if not page.render_image_path:
        raise HTTPException(status_code=404, detail=f"No rendered image for {book_id} page {page_number}")
    image_path = Path(page.render_image_path)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Image file missing on disk for {book_id} page {page_number}")
    return FileResponse(image_path, media_type="image/png")


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {
        "id": job.id,
        "book_id": job.book_id,
        "state": job.state,
        "phase": job.phase,
        "current_page": job.current_page,
        "total_pages": job.total_pages,
        "error_message": job.error_message,
    }


@app.get("/healthz")
def health() -> dict:
    return {"status": "ok"}
