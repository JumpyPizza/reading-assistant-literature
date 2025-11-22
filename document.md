Reading Assistant for Hard-to-Read Literary Books
Version: v0.1, the Parsing part Only, Local-Only Deployment

1. Scope & Goals

This document specifies the parsing subsystem for a reading assistant focused on hard-to-read literary books (e.g., translated philosophy).

We cover:

How uploaded PDFs are parsed and persisted.

How structure, layout, figures, and tables are represented.

How parsing jobs are managed, paused, resumed, and failed.

How text is indexed for later retrieval (full-text + vector stubs).

We explicitly do not cover:

Reader UI implementation.

LLM prompt design, text rewriting, recaps.

Retrieval-based review logic (question generation, evidence answers).

Remote storage or distributed deployment.

Everything is designed for local-only use:

Local filesystem storage (no S3).

Local SQL database (e.g., SQLite or Postgres run locally).

2. Functional Requirements
2.1 Parsing

Accept arbitrary book PDFs:

Digital, scanned, or mixed.

Convert all readable content into searchable text.

Detect and preserve:

Figures (images/illustrations).

Tables.

Their relative position in the original layout.

Retain original layout at page level:

Pages have dimensions and positions of blocks.

Reader can reconstruct a layout similar to original.

Parsing can be:

Started.

Paused.

Resumed.

Failed with an error reason.

All parsed results are persisted:

Text, structure, bounding boxes.

References to layout.

Extracted assets (images for figures/tables).

2.2 Indexing

Build a full-text index so we can later:

Search within a book.

Retrieve relevant passages for LLM-based features.

Provide hooks for:

Multimodal embeddings.

Vector DB integration (implementation can be deferred, but the interface should be clear).

3. High-Level Architecture
3.1 Components

Job Manager

Accepts an input PDF.

Creates Book and ParseJob records.

Places a job into a local work queue (or calls worker directly for v1).

Worker Engine

Dequeues a ParseJob.

Uses a pluggable Parsing Engine, initially:

Docling + RapidOCR.

Produces a structured in-memory representation of the book.

Persistently ingests this representation into the database in page batches.

Triggers full-text indexing after ingestion.

Parsing Engine (Pluggable)

Abstracts the underlying parser.

v1 implementation: Docling + RapidOCR.

Future implementations (MinerU, Unstructured, etc.) must conform to the same output format:

Pages

Sections

Blocks

Assets (figures, tables)

Asset Storage

Local filesystem directory hierarchy.

Stores:

Original PDF.

Page render images.

Extracted asset images (figures, table snapshots).

Database

Local SQL (e.g. SQLite or Postgres).

Stores:

Users.

Book metadata.

Parse jobs.

Pages, sections, blocks, assets.

Indexing statuses.

Indexing Layer

Whoosh for full-text search (local index on disk).

Stub/interface for vector DB; actual vector index can be added later.

4. Data Model & Database Schema

All tables are conceptual; types can be adapted to your SQL engine.
Primary keys are integers or UUIDs; pick one and apply consistently.

4.1 Users

Used for ownership; authentication details may be delegated to Supabase or another auth provider.

Table: users

id – primary key.

username – unique.

email.

password_hash – or external auth reference.

created_at.

updated_at.

(For local-only dev, this can be minimal or replaced by Supabase-managed user tables.)

4.2 Books & Parse Jobs
4.2.1 Books

Represents a logical book uploaded by a user.

Table: books

id – primary key.

user_id – foreign key → users.id.

file_md5 – CHAR(32), MD5 checksum for deduplication.

title – text (user input).

author – text, nullable (user input or parsed from PDF metadata).

source – TEXT or enum; values:

'upload'

'url'

original_file_path – text; path on local filesystem, e.g. books/{book_id}/original.pdf.

page_count – integer; set during precheck.

language – short code, e.g. "en", "zh".

parse_version – text; identifies parser and OCR version used, e.g. "docling-2.6+rapidocr-ppocrv4".

status – text or enum; values:

'uploaded'

'parsing'

'paused'

'parsed'

'failed'

'needs_reparse'

created_at.

updated_at.

4.2.2 Parse Jobs

Represents the lifecycle of parsing a single book.

Table: parse_jobs

id – primary key.

book_id – foreign key → books.id.

state – text or enum:

'queued'

'running'

'paused'

'completed'

'failed'

phase – text or enum:

'precheck'

'docling_parse'

'db_ingestion'

'indexing'

current_page – integer; last successfully ingested page number (0 if none).

total_pages – integer; copy of books.page_count for convenience.

error_message – text, nullable; last error description.

started_at – timestamp, nullable.

updated_at – timestamp.

config_json – JSON; snapshot of parsing configuration (language hint, OCR options, etc.).

4.3 Book Details: Pages, Sections, Blocks, Assets
4.3.1 Pages

One entry per PDF page.

Table: pages

id – primary key.

book_id – foreign key → books.id.

page_number – integer, 1-based.

width – float; width in original PDF units.

height – float; height in original PDF units.

render_image_path – text; path to full-res rendered page image, e.g. books/{book_id}/pages/{page_number}.png.

thumbnail_image_path – text; path to smaller thumbnail, e.g. books/{book_id}/pages/{page_number}_thumb.png.

parse_status – text or enum:

'parsed'

'failed'

'skipped'

created_at.

updated_at.

Decision: For v1, we store layout in page units (original PDF coordinate system).
Reader can later convert to pixel coordinates by scaling to viewport size.

4.3.2 Sections

Semantic structure (chapters, sections, subsections) inferred by the parser.

Table: sections

id – primary key.

book_id – foreign key → books.id.

parent_section_id – foreign key → sections.id, nullable (top-level sections).

level – integer; e.g. 1=chapter, 2=section, 3=subsection.

title_text – text; the section heading.

start_page_number – integer; first page where this section appears.

end_page_number – integer; last page where this section appears.

order_index – integer; TOC order within the book.

created_at.

updated_at.

Note: The parser engine is responsible for providing a section hierarchy; the worker maps it into sections.

4.3.3 Blocks

Blocks are the smallest layout units we care about for rendering and search: paragraphs, headings, tables, figures, captions, etc.

Table: blocks

id – primary key.

book_id – foreign key → books.id.

page_id – foreign key → pages.id.

section_id – foreign key → sections.id, nullable.

block_type – text or enum; examples:

'heading'

'paragraph'

'list_item'

'table'

'figure'

'caption'

'footnote'

'code'

'equation'

'quote'

'furniture' (headers, footers, page numbers)

text – text; plain text representation, used for full-text search.

markup – text, nullable; optional per-block Markdown or minimal HTML (for future reader/LLM formatting).

bbox_x – float; x-coordinate in page units (origin is upper-left or lower-left, but the choice must be fixed and documented; recommend origin at top-left).

bbox_y – float.

bbox_w – float; width in page units.

bbox_h – float; height in page units.

reading_order – integer; defines reading order within page (and possibly across sections).

asset_id – foreign key → assets.id, nullable; points to associated asset image if the block is a figure or table.

source_id – text, nullable; engine-specific identifier for traceability (e.g., Docling item ID).

created_at.

updated_at.

Decision: We use page coordinate system for bounding boxes (same as PDF).
The renderer will map these to screen coordinates when displaying the page.

4.3.4 Assets

Assets are extracted visual elements, mainly figures and table snapshots rendered as images.

Table: assets

id – primary key.

book_id – foreign key → books.id.

page_id – foreign key → pages.id.

asset_type – text or enum; examples:

'figure'

'table_snapshot'

'equation_image'

file_path – text; path to the asset image, e.g. books/{book_id}/assets/{asset_id}.png.

bbox_x – float; bounding box in page units.

bbox_y – float.

bbox_w – float.

bbox_h – float.

block_id – foreign key → blocks.id; block that “owns” the asset.

created_at.

updated_at.

Decision:
For tables, we may store both:

A snapshot image (asset_type = 'table_snapshot') and

A text/structural representation in the blocks.text / blocks.markup fields.

4.4 Indexing Status

Full-text and vector indexing are stored on disk elsewhere; we keep only status flags in DB.

Table: index_status

id – primary key.

book_id – foreign key → books.id.

fulltext_indexed – boolean.

vector_indexed – boolean.

fulltext_index_version – text, nullable.

vector_index_version – text, nullable.

created_at.

updated_at.

5. Filesystem Layout (Local Storage)

All files are stored on the local filesystem under a configurable root directory:

Root: BOOK_STORAGE_ROOT (e.g. ./data/books).

Paths use the following convention:

Original PDF:
BOOK_STORAGE_ROOT/books/{book_id}/original.pdf

Parser intermediate output (optional debug):
BOOK_STORAGE_ROOT/books/{book_id}/docling_output.json

Rendered page images (full resolution, e.g. 150–300 DPI):
BOOK_STORAGE_ROOT/books/{book_id}/pages/{page_number}.png

Page thumbnails (smaller images, e.g. 150px width):
BOOK_STORAGE_ROOT/books/{book_id}/pages/{page_number}_thumb.png

Assets (figures, table snapshots, etc.):
BOOK_STORAGE_ROOT/books/{book_id}/assets/{asset_id}.png

Requirement: File paths stored in the DB (original_file_path, render_image_path, thumbnail_image_path, assets.file_path) must match the filesystem layout.

6. Parsing Engine Abstraction

To keep the system extensible, the parsing engine is abstracted behind a stable interface.

6.1 Parsed Book Domain Objects

The engine should output a structured object (in code) equivalent to these conceptual entities:

ParsedPage

page_number

width, height

ParsedSection

id (engine-level ID)

parent_id

level

title_text

start_page_number, end_page_number

order_index

ParsedBlock

id

page_number

block_type

text

markup (optional)

bbox (x, y, w, h in page units)

reading_order (integer)

section_path (list of section titles or IDs; used to assign section_id)

asset_id (engine-level, to link to assets)

source_id (engine-native ID)

metadata (free-form JSON; e.g. confidence scores)

ParsedAsset

id

page_number

asset_type

bbox

image_bytes or image path (depending on implementation)

metadata

ParsedBook

pages (list of ParsedPage)

sections (list of ParsedSection)

blocks (list of ParsedBlock)

assets (list of ParsedAsset)

engine_version (string)

metadata (free-form JSON, e.g. parser stats)

The worker ingests these objects into the database and filesystem.

6.2 Engine Responsibilities

The parsing engine is responsible for:

Running Docling + RapidOCR on the input PDF.

Determining:

Page dimensions.

Layout blocks and their bounding boxes.

Block types (paragraph, heading, table, figure, etc.).

Section hierarchy and section membership of blocks.

Association of figures/tables with text blocks (e.g. captions).

Providing reading order for blocks on each page.

Generating either:

Raw images for assets (figures, table snapshots), or

Enough bounding box metadata for the worker to crop assets from rendered pages.

For v1, we prefer the engine to supply bounding boxes, and the worker will handle actual image cropping from rendered page images. This keeps the engine implementation simpler and reuseable.

7. Worker Pipeline & Control Flow

The worker is responsible for:

Driving ParseJob through its phases.

Managing pausing and resuming.

Persisting all parsed content into DB + filesystem.

Triggering indexing.

7.1 Phases & States

Each job has:

state:

'queued'

'running'

'paused'

'completed'

'failed'

phase:

'precheck'

'docling_parse'

'db_ingestion'

'indexing'

Phase Transitions

Precheck

Verify:

books.original_file_path exists and is a readable PDF.

Read:

Page count using a lightweight PDF reader (not Docling).

Update:

books.page_count.

parse_jobs.total_pages.

Next:

Set phase = 'docling_parse'.

Docling Parse

Build configuration (language hint, OCR enabled).

Call the parsing engine to produce a ParsedBook.

Optionally serialize ParsedBook to JSON:

docling_output.json for debugging and manual re-ingestion.

Next:

Set phase = 'db_ingestion'.

Reset current_page = 0.

DB Ingestion (Batch & Pause-Capable)

Define a batch size N pages (default: 50).

Sort ParsedBook.pages by page_number.

For each batch:

For each page where page_number > current_page:

Insert pages row.

Insert corresponding sections for sections whose range covers this page (sections should be pre-created or created lazily; choose one strategy and document it).

Insert blocks for blocks belonging to this page, including bounding boxes, type, text.

For blocks that link to assets, insert assets entries and crop image regions from page render (see asset extraction below).

After every batch:

Commit DB transaction.

Update parse_jobs.current_page to the last ingested page number.

Check if parse_jobs.state == 'paused':

If yes, stop ingestion and leave phase = 'db_ingestion'.

Once all pages are ingested:

Set phase = 'indexing'.

Indexing

Full-text:

Iterate over all blocks.text for the book.

Index them in Whoosh:

At minimum, store:

book_id

block_id

text

Vector index (optional now, but design for later):

For now, can be a stub; later will:

Chunk blocks into semantic chunks.

Compute embeddings.

Store them in a local or remote vector DB.

Once indexing is complete:

Set parse_jobs.state = 'completed'.

Set books.status = 'parsed'.

Update index_status accordingly.

Failure Handling

If any phase raises an exception:

Set parse_jobs.state = 'failed'.

Set books.status = 'failed'.

Store the error string in parse_jobs.error_message.

7.2 Pausing & Resuming

Pausing

The job manager or user sets parse_jobs.state = 'paused'.

The worker, during DB ingestion and indexing, must periodically:

Re-read parse_jobs.state from DB (or from in-memory cache updated by a heartbeat).

If it sees 'paused', it:

Completes the current batch.

Commits all changes.

Exits the job loop.

Resuming

To resume, the job manager sets:

parse_jobs.state = 'queued'.

Worker picks up the job again.

Based on the current phase:

If phase = 'db_ingestion', the worker:

Re-runs the Docling parse (to obtain a fresh ParsedBook).

Uses parse_jobs.current_page to decide where to restart ingestion:

Only ingest pages where page_number > current_page.

If phase = 'indexing', full-text indexing should be idempotent:

Either re-index all blocks for that book, or only ones that are missing (depending on design of Whoosh integration).

7.3 Tracking Progress

For user feedback:

Use:

parse_jobs.current_page and total_pages → percentage done during DB ingestion.

During docling_parse:

Docling itself may not expose granular progress through the Python API.

For v1, treat docling_parse as a single step:

Show status like "Parsing structure...".

Later improvements:

Use Docling logs if available (e.g. run in subprocess, parse stdout for "Page X/Y").

This is optional and can be added later.

7.4 Asset Extraction Strategy

Two options; v1 should pick one and be consistent.

Engine Provides Asset Images

Engine (Docling) outputs ParsedAsset objects with image_bytes.

Worker writes those directly to books/{book_id}/assets/{asset_id}.png.

Advantages:

Fewer dependencies in worker.

Disadvantages:

Ties pipeline more closely to Docling’s internal image export.

Worker Crops Assets from Page Render Images (Recommended for v1)

Pipeline:

After or during page insertion, render each page to a full image using a PDF renderer (e.g., via a separate tool; exact implementation detail is outside of this spec).

For each ParsedAsset from engine:

Use its bbox in page units to crop from the rendered page image.

Save crop as books/{book_id}/assets/{asset_id}.png.

Insert assets row with references and bounding boxes.

Advantages:

Engine only needs to provide precise bounding boxes.

Cropping process is unified and independent of parsing engine.

For this design, we assume Option 2: worker crops from rendered page images.

8. Indexing Details (v1)
8.1 Full-Text Index (Whoosh)

One Whoosh index for all books, with fields such as:

book_id (stored).

block_id (stored).

text (indexed, tokenized).

When indexing:

For each block:

Use blocks.text as the main content.

Optionally add section_id or page_number as stored fields.

Searching:

Later, the reader or review engine can:

Query the Whoosh index with keywords.

Receive back block_id and book_id.

Load the corresponding blocks from DB.

8.2 Vector Index (Stub)

For now:

Provide a function or module that:

Given a book_id, returns all blocks (or later, semantic chunks).

A later implementation can:

Compute embeddings.

Insert into a vector index store (e.g., local FAISS file).

Store only a status in index_status:

vector_indexed = false for v1.

9. Non-Functional Requirements

Local-only:

No external services required.

All storage is on local filesystem and local SQL DB.

Idempotent ingestion:

Re-running ingestion from phase = 'db_ingestion' should not corrupt data.

Either:

Delete previous partial rows for that book_id before re-ingesting, or

Perform existence checks and skip duplicates.

Extensibility:

Parsing engine can be replaced without changing:

DB schema.

Storage layout.

Indexing implementation.

Error visibility:

parse_jobs.error_message must contain a concise description of the last failure.

Local logs (files or stdout) should have stack traces in debug mode.

10. Summary of Key Design Decisions

Parsing engine is pluggable; v1 uses Docling + RapidOCR.

Engine outputs a ParsedBook structure (pages, sections, blocks, assets).

Worker:

Drives the ParseJob through phases.

Handles pause/resume at batch boundaries for DB ingestion.

Layout:

Stored at page level via bounding boxes in original PDF coordinates.

Figures & tables:

Represented as blocks + optional assets (image files).

Kept at their original position via bounding boxes.

Indexing:

Full-text indexing with Whoosh.

Vector indexing is stubbed for future extension.

Storage:

All files stored in a consistent directory structure under BOOK_STORAGE_ROOT.

DB tables define a complete, engine-agnostic representation of the parsed book.