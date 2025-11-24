### A reading assistant for hard-to-read literary books (e.g., translated philosophy)
It does the following: 

1. Parsing
- Parse Arbitrary book PDFs (digital or scanned or mixed)
    - Parsing can be paused/resumed
- Index the texts, figures and tables
- Keep figures and tables in original position
- Retain Original layout
- Save results 
2. Reader
- A simple customized reader that: 
    - Show the content roughly in the same layout as original book
    - Rewrite the text with higher readability for the reader to enjoy reading
    - Generate recap after some length 
    - Keep note, of course (or maybe connect to Notion)
3. Retrieval-based Review: 
- Generate questions/discussions (like the original writer chats with the reader while having tea together)
- Answer with evidence: answer something by quoting views from the book 

----
### Architecture
#### Parsing   
1. Job Manager
    - accepts an input file (PDF only for now)
    - Creates a parseJob + Book record
    - Enqueues work for workers
2. Worker Engine 
    - Use Docling + RapidOCR
    Note: design this to be plug-in style, so we can freely replace it with other parsers
3. Asset Storage
    - stores original pdf, extracted items (figures, table snapshots)
    - Database for: 
        - book metadata   
        - pages
        - blocks (paragraphs, headings, tables index, figures index)
        - layout
        - parse job state
4. Indexing
    - Full-text indexing (Whoosh for now)
    - Multimodal embedding; Vector DB 

#### Database 
1. User information 
    - User field, user_name/account/password/user_id/etc..
2. Parse Job
    - id
    - book_id
    - state (queued / running / paused / completed / failed)
    - current_page (last successfully processed page)
    - total_pages 
    - error_message
    - started_at, updated_at
    - phase (struct_parse, asset_extract, indexing)
    - worker_id (optional; leave this out for now as the system is small)

3. Book Info 
    - id
    - user_id (owner)
    - file MD5 (for deduplication)
    - title (user input)
    - author (optional, user input or parsed)
    - source (upload/url)
    - page_count (added by the parser engine)
    - language (supports EN, ZH now)
    - parse_version (e.g. “docling-v1.0-rapidocr-ppocrv4”, indicates the parsing and OCR engine)
    - status (parsed / parsing / failed / needs_reparse)
    - created_at, updated_at
    - Maybe some others? Get it when needed

4. Book Details   
    1. Page 
    - id
    - book_id
    - page_number
    - width, height (PDF units)
    - render_image_path (full-resolution image)
    - thumbnail_image_path
    - parse_status (parsed, failed, skipped)
    - created_at, updated_at  
    2. Section (structure parsed by the engine, adjust based on parser doc)  
    - id
    - book_id
    - parent_section_id (nullable for top-level)
    - level (1=chapter, 2=section, etc.)
    - title_text
    - start_page_number, end_page_number
    - order_index
    3. Block (contents of the sections)
    - id
    - book_id
    - page_id
    - section_id (nullable if not yet attached)
    - block_type (e.g. heading, paragraph, list_item, table, figure, caption, footnote, code, equation, quote, furniture (header/footer) etc.)
    - text (plain text for search)
    - bbox_x, bbox_y, bbox_w, bbox_h (normalized 0–1 or in page units)
    - reading_order (global order on the page or within section)
    - asset_id (nullable; for figure/table snapshots) 
    - source_id / docling_id (optional pointer back to Docling item)
    4. Asset
    - id
    - book_id
     -page_id
    - asset_type (figure, table_snapshot, equation_image, etc.)
    - file_path
    - bbox_x, bbox_y, bbox_w, bbox_h
    - block_id (the block that “owns” this asset, usually a figure or table)

5. API for data exchange (with reader and LLM)
    These APIs define how our reader retrieves parsed book and render it; basically it defines how the parsed data is exchanged 

#### Reader 
A browser-based, front-end reader, that:
shows the original pdf (one page) at the left side;
shows the rephrased content of this page at the right side;


#### RAG 
TO Be added 

### Workder pipeline
1. a book is updated, pipeline triggered 
2. precheck: if new book; if parse job exists but paused; if create a new job: can open PDF, count pages, create databases; 
3. parsing
    1. structural parse using engine (Docling/ + OCR for scanned); track progress here via log monitoring (capturing stdout) so the user knows it's not stuck. Docling blocks execution, run it in a subprocess. Parse logs looking for "Page X/Y". Update DB: Update status_msg = "Analyzing structure: Page X/Y" every few seconds.  Save the resulting output (e.g. JSON )to temp_out_path. Update Job phase = 2_db_ingestion.
    2. Streaming Ingestion (Batch & Pause Capable)
    - worker loads the temp_out_path.
    - Identify start_page based on Job's current_page (0 if new, X if resuming).
    - Insert Page record.
    - Process Blocks: Iterate blocks in JSON. Calculate Section hierarchy (or is this returned directly by docling?). Insert Block records.
    - Extract Assets: If block is figure or table: Use bbox coordinates, Open original PDF (via pdf2image or similar), crop the specific area, Save image to storage.
    - Insert Asset record.
    3. indexing, full-text indexing
4. finished, return state: success/failed; 
5. failure handling: If any step raises an Exception, update Job status = failed, save traceback to error_log.
5. if status == paused, stop the worker, save status.


