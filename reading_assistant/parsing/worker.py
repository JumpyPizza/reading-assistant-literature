from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .engine import ParsingEngine
from .indexing import Indexer
from .models import (
    AssetRecord,
    BlockRecord,
    BookStatus,
    PageRecord,
    ParseJobPhase,
    ParseJobState,
    ParsedAsset,
    ParsedBlock,
    ParsedBook,
    ParsedSection,
    SectionRecord,
)
from .repository import ParsingRepository
from .storage import LocalBookStorage


class ParsingWorker:
    """
    Drives a parse job through precheck -> parse -> DB ingestion -> indexing.
    The worker is stateless and relies on the repository for job/book state
    and on the storage adapter for filesystem operations.
    """

    def __init__(
        self,
        repository: ParsingRepository,
        storage: LocalBookStorage,
        engine: ParsingEngine,
        indexer: Indexer,
        batch_size: int = 50,
        persist_engine_output: bool = True,
    ):
        self.repo = repository
        self.storage = storage
        self.engine = engine
        self.indexer = indexer
        self.batch_size = batch_size
        self.persist_engine_output = persist_engine_output

    def run_job(self, job_id: str) -> None:
        job = self.repo.get_job(job_id)
        if not job:
            raise ValueError(f"Parse job {job_id} not found")
        book = self.repo.get_book(job.book_id)
        if not book:
            raise ValueError(f"Book {job.book_id} not found for job {job_id}")

        pdf_path = self._locate_pdf(book.original_file_path, book.id)
        try:
            self.repo.update_job_state_phase(job_id, state=ParseJobState.RUNNING, phase=ParseJobPhase.PRECHECK)
            self.repo.update_book_status(book.id, BookStatus.PARSING)

            page_count = self._determine_page_count(pdf_path)
            self.repo.update_book_status(book.id, BookStatus.PARSING, page_count=page_count)
            self.repo.update_job_state_phase(job_id, total_pages=page_count)

            self.repo.update_job_state_phase(job_id, phase=ParseJobPhase.DOCLING_PARSE)
            parsed_book = self.engine.parse(pdf_path)

            if self.persist_engine_output:
                self.storage.write_docling_output(book.id, json.loads(json.dumps(parsed_book, default=self._json_default)))

            self.repo.update_job_state_phase(job_id, phase=ParseJobPhase.DB_INGESTION)
            self._ingest_parsed_book(job_id, book.id, parsed_book, resume_from_page=job.current_page)

            self.repo.update_job_state_phase(job_id, phase=ParseJobPhase.INDEXING)
            blocks = self.repo.list_blocks_for_book(book.id)
            self.indexer.index_book(book.id, blocks)

            self.repo.update_job_state_phase(job_id, state=ParseJobState.COMPLETED)
            self.repo.update_book_status(book.id, BookStatus.PARSED)
        except Exception as exc:  # noqa: BLE001
            self.repo.update_job_state_phase(job_id, state=ParseJobState.FAILED, error_message=str(exc))
            self.repo.update_book_status(book.id, BookStatus.FAILED)
            raise

    def _locate_pdf(self, book_original_path: str, book_id: str) -> Path:
        stored = self.storage.find_original_pdf(book_id)
        candidate = stored if stored else Path(book_original_path)
        if not candidate.exists():
            raise FileNotFoundError(f"PDF not found at {candidate}")
        return candidate

    def _determine_page_count(self, pdf_path: Path) -> Optional[int]:
        count = self.engine.count_pages(pdf_path)
        return count

    def _json_default(self, obj):
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

    def _ingest_parsed_book(
        self,
        job_id: str,
        book_id: str,
        parsed_book: ParsedBook,
        resume_from_page: int = 0,
    ) -> None:
        pages_sorted = sorted(parsed_book.pages, key=lambda p: p.page_number)
        sections_sorted = sorted(parsed_book.sections, key=lambda s: s.order_index if hasattr(s, "order_index") else 0)
        page_id_map: Dict[int, str] = {}
        section_id_map: Dict[str, str] = {}

        # Sections are book-level, so we upsert them once.
        section_records = self._map_sections(book_id, sections_sorted, section_id_map)
        if section_records:
            self.repo.upsert_sections(section_records)

        batch_pages: List[PageRecord] = []
        batch_blocks: List[BlockRecord] = []
        batch_assets: List[AssetRecord] = []
        last_page_ingested = resume_from_page

        for page in pages_sorted:
            if page.page_number <= resume_from_page:
                continue
            page_id = f"{book_id}-p{page.page_number}"
            page_id_map[page.page_number] = page_id
            page_record = PageRecord(
                id=page_id,
                book_id=book_id,
                page_number=page.page_number,
                width=page.width,
                height=page.height,
                render_image_path=None,
                thumbnail_image_path=None,
                parse_status="parsed",
            )
            batch_pages.append(page_record)

            related_blocks = [b for b in parsed_book.blocks if b.page_number == page.page_number]
            block_records, asset_owner_map = self._map_blocks(
                book_id=book_id,
                page_id=page_id,
                blocks=related_blocks,
                section_id_map=section_id_map,
            )
            batch_blocks.extend(block_records)

            related_assets = [a for a in parsed_book.assets if a.page_number == page.page_number]
            asset_records = self._map_assets(book_id, page_id, related_assets, asset_owner_map)
            batch_assets.extend(asset_records)

            # Commit batch when reaching batch_size or end.
            if len(batch_pages) >= self.batch_size:
                self.repo.upsert_pages(batch_pages)
                self.repo.upsert_blocks(batch_blocks)
                self.repo.upsert_assets(batch_assets)
                last_page_ingested = page.page_number
                self.repo.update_job_state_phase(job_id, current_page=last_page_ingested)
                batch_pages, batch_blocks, batch_assets = [], [], []
                if self._should_pause(job_id):
                    return

        # Final flush
        if batch_pages:
            self.repo.upsert_pages(batch_pages)
            self.repo.upsert_blocks(batch_blocks)
            self.repo.upsert_assets(batch_assets)
            last_page_ingested = batch_pages[-1].page_number
            self.repo.update_job_state_phase(job_id, current_page=last_page_ingested)
            if self._should_pause(job_id):
                return

    def _should_pause(self, job_id: str) -> bool:
        job = self.repo.get_job(job_id)
        return bool(job and job.state == ParseJobState.PAUSED)

    def _map_sections(
        self,
        book_id: str,
        parsed_sections: List[ParsedSection],
        section_id_map: Dict[str, str],
    ) -> List[SectionRecord]:
        records: List[SectionRecord] = []
        for section in parsed_sections:
            record_id = f"{book_id}-sec-{section.id}"
            section_id_map[section.id] = record_id
            parent_id = None
            if section.parent_id:
                parent_id = section_id_map.get(section.parent_id, f"{book_id}-sec-{section.parent_id}")
            records.append(
                SectionRecord(
                    id=record_id,
                    book_id=book_id,
                    parent_section_id=parent_id,
                    level=section.level,
                    title_text=section.title_text,
                    start_page_number=section.start_page_number,
                    end_page_number=section.end_page_number,
                    order_index=section.order_index,
                )
            )
        return records

    def _map_blocks(
        self,
        book_id: str,
        page_id: str,
        blocks: List[ParsedBlock],
        section_id_map: Dict[str, str],
    ) -> Tuple[List[BlockRecord], Dict[str, str]]:
        records: List[BlockRecord] = []
        asset_owner_map: Dict[str, str] = {}
        for block in blocks:
            block_id = f"{book_id}-blk-{block.id}"
            section_id = self._resolve_section(block, section_id_map)
            asset_ref = f"{book_id}-asset-{block.asset_id}" if block.asset_id else None
            if asset_ref:
                asset_owner_map[asset_ref] = block_id
            records.append(
                BlockRecord(
                    id=block_id,
                    book_id=book_id,
                    page_id=page_id,
                    section_id=section_id,
                    block_type=block.block_type,
                    text=block.text,
                    markup=block.markup,
                    bbox_x=block.bbox.x,
                    bbox_y=block.bbox.y,
                    bbox_w=block.bbox.w,
                    bbox_h=block.bbox.h,
                    reading_order=block.reading_order,
                    asset_id=asset_ref,
                    source_id=block.source_id,
                )
            )
        return records, asset_owner_map

    def _map_assets(
        self,
        book_id: str,
        page_id: str,
        assets: List[ParsedAsset],
        asset_owner_map: Dict[str, str],
    ) -> List[AssetRecord]:
        records: List[AssetRecord] = []
        for asset in assets:
            asset_id = f"{book_id}-asset-{asset.id}"
            file_path = ""
            if asset.image_bytes:
                path = self.storage.write_asset_image(book_id, asset_id, asset.image_bytes)
                file_path = str(path)
            elif asset.image_path:
                file_path = str(asset.image_path)
            records.append(
                AssetRecord(
                    id=asset_id,
                    book_id=book_id,
                    page_id=page_id,
                    asset_type=asset.asset_type,
                    file_path=file_path,
                    bbox_x=asset.bbox.x,
                    bbox_y=asset.bbox.y,
                    bbox_w=asset.bbox.w,
                    bbox_h=asset.bbox.h,
                    block_id=asset_owner_map.get(asset_id),
                )
            )
        return records

    def _resolve_section(self, block: ParsedBlock, section_id_map: Dict[str, str]) -> Optional[str]:
        for section_ref in block.section_path:
            if section_ref in section_id_map:
                return section_id_map[section_ref]
        return None
