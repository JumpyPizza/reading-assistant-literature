from __future__ import annotations

from fastapi import APIRouter, HTTPException

from reading_assistant.parsing import BookStatus, ParseJobState
from api.dependencies import get_storage, get_indexer

from api.dependencies import get_repo

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(job_id: str):
    repo = get_repo()
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


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str):
    repo = get_repo()
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    book = repo.get_book(job.book_id)
    if not book:
        raise HTTPException(status_code=404, detail=f"Book not found for job: {job.book_id}")

    repo.update_job_state_phase(job_id, state=ParseJobState.FAILED, error_message="Cancelled by user")
    repo.update_book_status(book.id, BookStatus.FAILED)
    # Clean up storage, index, and DB records.
    get_storage().delete_book(book.id)
    get_indexer().delete_book(book.id)
    repo.delete_book(book.id)
    return {"status": "cancelled", "job_id": job_id, "book_id": book.id}
