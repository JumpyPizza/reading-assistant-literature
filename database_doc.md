# Database Tables

## books
- Purpose: stores each uploaded document and its parse lifecycle state.
- Fields: `id` (PK), `user_id`, `file_md5`, `title`, `author`, `source`, `original_file_path`, `language`, `parse_version`, `status` enum (`uploaded|parsing|paused|parsed|failed|needs_reparse`), `page_count`, `created_at`, `updated_at`.

## parse_jobs
- Purpose: tracks background parsing for a specific book.
- Fields: `id` (PK), `book_id`, `state` enum (`queued|running|paused|completed|failed`), `phase` enum (`precheck|docling_parse|db_ingestion|indexing`), `current_page`, `total_pages`, `error_message`, `started_at`, `updated_at`, `config_json` (stringified JSON config).

## pages
- Purpose: per-page geometry and rendered artifacts.
- Fields: `id` (PK, e.g., `{book_id}-p{n}`), `book_id`, `page_number`, `width`, `height`, `render_image_path`, `thumbnail_image_path`, `parse_status`, `created_at`, `updated_at`.

## sections
- Purpose: document outline and hierarchy.
- Fields: `id` (PK, e.g., `{book_id}-sec-{section_id}`), `book_id`, `parent_section_id`, `level`, `title_text`, `start_page_number`, `end_page_number`, `order_index`, `created_at`, `updated_at`.

## blocks
- Purpose: text blocks with layout positioning per page.
- Fields: `id` (PK, e.g., `{book_id}-blk-{block_id}`), `book_id`, `page_id`, `section_id`, `block_type`, `text`, `markup`, `bbox_x`, `bbox_y`, `bbox_w`, `bbox_h`, `reading_order`, `asset_id`, `source_id`, `created_at`, `updated_at`.

## assets
- Purpose: non-text assets such as images/figures/tables linked to blocks/pages.
- Fields: `id` (PK, e.g., `{book_id}-asset-{asset_id}`), `book_id`, `page_id`, `asset_type`, `file_path`, `bbox_x`, `bbox_y`, `bbox_w`, `bbox_h`, `block_id`, `created_at`, `updated_at`.

## Connection
- Default DB URL comes from `DATABASE_URL` (defaults to `sqlite+pysqlite:///./data/reading_assistant.db`).
