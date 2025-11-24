# Reader Frontend (Flutter Web)

Upload → parse → read in one app. Desktop shows side-by-side original and parsed text; mobile uses swipe (PageView) between the two panes. The upload card triggers the FastAPI upload endpoint, polls job status, and shows a “Read book” button when parsing completes.

## Endpoints expected
Replace `baseUrl` in `lib/main.dart` with your FastAPI host. Endpoints:

- `POST /documents/upload` (multipart) → returns `{ "book_id": "...", "job_id": "..." }`
  - form fields: `title`, optional `author`, `language`, `perform_ocr`
  - file field: `file` (PDF)
- `GET /jobs/{job_id}` → returns job state with `state`, `phase`, `current_page`, `total_pages`, `error_message`, `book_id`
- `GET /documents/{doc_id}/pages/{page}/image` → rendered page image (PNG/JPEG)
- `GET /documents/{doc_id}/pages/{page}/parsed` → parsed page JSON:
  ```json
  {
    "page": 1,
    "width": 612,
    "height": 792,
    "blocks": [
      { "id": "blk-1", "block_type": "paragraph", "reading_order": 0, "text": "First paragraph" }
    ]
  }
  ```

## Run locally
```
cd frontend/reader
flutter pub get
flutter run -d chrome
```

## Notes
- Zoom/pan is supported on the left via `InteractiveViewer`.
- Parsed blocks are sorted by `reading_order` client-side; missing `text` raises an error to avoid silent fallbacks.
