# API Reference

## GET /healthz
- Purpose: liveness check; returns `{"status":"ok"}`.

## GET /documents
- Purpose: list parsed books.
- Response: array of `{id, title, author, language, page_count, status}`. Only books with status `parsed` are returned.

## GET /documents/{book_id}
- Purpose: fetch metadata for a book.
- Response: `{id, title, author, language, page_count, status}`. Returns 404 if the book is missing.

## GET /documents/{book_id}/pages/{page_number}/parsed
- Purpose: fetch parsed content for a specific page.
- Response: `{page, width, height, blocks:[{id, block_type, reading_order, text, bbox, section_id, asset_id}]}` where `bbox` is `[x,y,w,h]`. 404 if page or blocks are missing.

## GET /documents/{book_id}/pages/{page_number}/image
- Purpose: fetch the rendered PNG image for a page.
- Response: PNG binary. 404 if the rendered image is missing.

## GET /documents/{book_id}/search
- Purpose: full-text search over indexed blocks for the book.
- Query params: `query` (required), `limit` (optional, default 20).
- Response: `{hits:[{block_id, page_id, page_number, reading_order, text}]}`.

## POST /documents/upload
- Purpose: upload a PDF and enqueue parsing.
- Body (multipart form): `file` (PDF, required), `title` (required), `author` (optional), `language` (default `en`), `perform_ocr` (bool, default `false`).
- Response: `{book_id, job_id}`. Background job is started automatically.

## GET /jobs/{job_id}
- Purpose: fetch parse job status/progress.
- Response: `{id, book_id, state, phase, current_page, total_pages, error_message}`. 404 if missing.

## POST /jobs/{job_id}/cancel
- Purpose: cancel a parse job and clean up data.
- Effect: marks job failed, marks book failed, removes stored files/index/DB rows.
- Response: `{status:"cancelled", job_id, book_id}`.
