from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from reading_assistant.parsing import (
    BookRecord,
    BookStatus,
    ParseJobPhase,
    ParseJobRecord,
    ParseJobState,
)

from api.dependencies import (
    build_book_id,
    build_worker,
    compute_md5_bytes,
    get_indexer,
    get_repo,
    get_storage,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_repo():
    return get_repo()


def _get_storage():
    return get_storage()


def _get_indexer():
    return get_indexer()


@router.get("")
def list_documents():
    repo = _get_repo()
    books = repo.list_books()
    parsed = [b for b in books if b.status == BookStatus.PARSED]
    return [
        {
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "language": b.language,
            "page_count": b.page_count,
            "status": b.status,
        }
        for b in parsed
    ]


@router.get("/{book_id}")
def get_document(book_id: str):
    repo = _get_repo()
    book = repo.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail=f"Book not found: {book_id}")
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "language": book.language,
        "page_count": book.page_count,
        "status": book.status,
    }


@router.get("/{book_id}/pages/{page_number}/parsed")
def get_parsed_page(book_id: str, page_number: int):
    repo = _get_repo()
    page = repo.get_page(book_id, page_number)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page not found: {book_id} page {page_number}")
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


@router.get("/{book_id}/pages/{page_number}/image")
def get_page_image(book_id: str, page_number: int):
    repo = _get_repo()
    page = repo.get_page(book_id, page_number)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page not found: {book_id} page {page_number}")
    if not page.render_image_path:
        raise HTTPException(status_code=404, detail=f"No rendered image for {book_id} page {page_number}")
    image_path = Path(page.render_image_path)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Image file missing on disk for {book_id} page {page_number}")
    return FileResponse(image_path, media_type="image/png")


@router.get("/{book_id}/search")
def search_document(book_id: str, query: str, limit: int = 20):
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")
    repo = _get_repo()
    book = repo.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail=f"Book not found: {book_id}")

    results = _get_indexer().search(f"{query}", limit=limit)
    hits = []
    for hit in results:
        page_id = hit.get("page_id") or ""
        page_number = 0
        if "-p" in page_id:
            try:
                page_number = int(page_id.split("-p")[-1])
            except Exception:
                page_number = 0
        hits.append(
            {
                "block_id": hit.get("block_id"),
                "page_id": page_id,
                "page_number": page_number,
                "reading_order": int(hit.get("reading_order") or 0),
                "text": hit.get("text") or "",
            }
        )
    return {"hits": hits}


@router.post("/upload")
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

    repo = _get_repo()
    storage = _get_storage()
    book_id = build_book_id(title)
    if repo.get_book(book_id):
        raise HTTPException(status_code=409, detail=f"Book already exists: {book_id}")

    tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=".pdf")
    tmp_path = Path(tmp_path_str)
    with os.fdopen(tmp_fd, "wb") as tmp_file:
        tmp_file.write(payload)

    storage.ensure_base_dirs(book_id)
    original_pdf_path = storage.save_original_pdf(book_id, tmp_path)
    tmp_path.unlink(missing_ok=True)

    engine = build_worker(perform_ocr).engine
    book = BookRecord(
        id=book_id,
        user_id="upload-user",
        file_md5=compute_md5_bytes(payload),
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


def _run_job(job_id: str, perform_ocr: bool) -> None:
    worker = build_worker(perform_ocr)
    worker.run_job(job_id)
