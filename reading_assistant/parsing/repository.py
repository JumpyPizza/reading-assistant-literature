from __future__ import annotations

import json
from copy import deepcopy
from typing import Dict, Iterable, List, Optional

from sqlalchemy import Column, DateTime, Enum, Float, String, create_engine, select, update
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .models import (
    AssetRecord,
    BlockRecord,
    BookRecord,
    BookStatus,
    PageRecord,
    ParseJobPhase,
    ParseJobRecord,
    ParseJobState,
    SectionRecord,
)

Base = declarative_base()


class BookModel(Base):
    __tablename__ = "books"
    id = Column(String, primary_key=True)
    user_id = Column(String)
    file_md5 = Column(String)
    title = Column(String)
    author = Column(String)
    source = Column(String)
    original_file_path = Column(String)
    language = Column(String)
    parse_version = Column(String)
    status = Column(Enum(BookStatus))
    page_count = Column(Float)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class ParseJobModel(Base):
    __tablename__ = "parse_jobs"
    id = Column(String, primary_key=True)
    book_id = Column(String, index=True)
    state = Column(Enum(ParseJobState))
    phase = Column(Enum(ParseJobPhase))
    current_page = Column(Float)
    total_pages = Column(Float)
    error_message = Column(String)
    started_at = Column(DateTime)
    updated_at = Column(DateTime)
    config_json = Column(String)


class PageModel(Base):
    __tablename__ = "pages"
    id = Column(String, primary_key=True)
    book_id = Column(String, index=True)
    page_number = Column(Float)
    width = Column(Float)
    height = Column(Float)
    render_image_path = Column(String)
    thumbnail_image_path = Column(String)
    parse_status = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class SectionModel(Base):
    __tablename__ = "sections"
    id = Column(String, primary_key=True)
    book_id = Column(String, index=True)
    parent_section_id = Column(String)
    level = Column(Float)
    title_text = Column(String)
    start_page_number = Column(Float)
    end_page_number = Column(Float)
    order_index = Column(Float)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class BlockModel(Base):
    __tablename__ = "blocks"
    id = Column(String, primary_key=True)
    book_id = Column(String, index=True)
    page_id = Column(String, index=True)
    section_id = Column(String)
    block_type = Column(String)
    text = Column(String)
    markup = Column(String)
    bbox_x = Column(Float)
    bbox_y = Column(Float)
    bbox_w = Column(Float)
    bbox_h = Column(Float)
    reading_order = Column(Float)
    asset_id = Column(String)
    source_id = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class AssetModel(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True)
    book_id = Column(String, index=True)
    page_id = Column(String)
    asset_type = Column(String)
    file_path = Column(String)
    bbox_x = Column(Float)
    bbox_y = Column(Float)
    bbox_w = Column(Float)
    bbox_h = Column(Float)
    block_id = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class ParsingRepository:
    """
    Abstract persistence boundary for parsing. Implementations can target
    SQLite/Postgres or any other backing store. All methods are synchronous
    to keep the interface minimal for now.
    """

    # Book operations
    def get_book(self, book_id: str) -> Optional[BookRecord]:
        raise NotImplementedError

    def save_book(self, book: BookRecord) -> None:
        raise NotImplementedError

    def update_book_status(self, book_id: str, status: BookStatus, page_count: Optional[int] = None) -> None:
        raise NotImplementedError

    # Parse job operations
    def get_job(self, job_id: str) -> Optional[ParseJobRecord]:
        raise NotImplementedError

    def save_job(self, job: ParseJobRecord) -> None:
        raise NotImplementedError

    def update_job_state_phase(
        self,
        job_id: str,
        state: Optional[ParseJobState] = None,
        phase: Optional[ParseJobPhase] = None,
        current_page: Optional[int] = None,
        total_pages: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        raise NotImplementedError

    # Content ingestion
    def upsert_pages(self, pages: Iterable[PageRecord]) -> None:
        raise NotImplementedError

    def upsert_sections(self, sections: Iterable[SectionRecord]) -> None:
        raise NotImplementedError

    def upsert_blocks(self, blocks: Iterable[BlockRecord]) -> None:
        raise NotImplementedError

    def upsert_assets(self, assets: Iterable[AssetRecord]) -> None:
        raise NotImplementedError

    def list_blocks_for_book(self, book_id: str) -> List[BlockRecord]:
        raise NotImplementedError


class InMemoryParsingRepository(ParsingRepository):
    """
    Simple in-memory store for local runs and tests. It mirrors the DB shape
    and keeps copies of dataclasses to avoid cross-mutation between calls.
    """

    def __init__(self):
        self.books: Dict[str, BookRecord] = {}
        self.jobs: Dict[str, ParseJobRecord] = {}
        self.pages: Dict[str, PageRecord] = {}
        self.sections: Dict[str, SectionRecord] = {}
        self.blocks: Dict[str, BlockRecord] = {}
        self.assets: Dict[str, AssetRecord] = {}

    def _clone(self, obj):
        return deepcopy(obj)

    def get_book(self, book_id: str) -> Optional[BookRecord]:
        book = self.books.get(book_id)
        return self._clone(book) if book else None

    def save_book(self, book: BookRecord) -> None:
        self.books[book.id] = self._clone(book)

    def update_book_status(self, book_id: str, status: BookStatus, page_count: Optional[int] = None) -> None:
        book = self.books.get(book_id)
        if not book:
            return
        book.status = status
        if page_count is not None:
            book.page_count = page_count
        self.books[book_id] = self._clone(book)

    def get_job(self, job_id: str) -> Optional[ParseJobRecord]:
        job = self.jobs.get(job_id)
        return self._clone(job) if job else None

    def save_job(self, job: ParseJobRecord) -> None:
        self.jobs[job.id] = self._clone(job)

    def update_job_state_phase(
        self,
        job_id: str,
        state: Optional[ParseJobState] = None,
        phase: Optional[ParseJobPhase] = None,
        current_page: Optional[int] = None,
        total_pages: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return
        if state is not None:
            job.state = state
        if phase is not None:
            job.phase = phase
        if current_page is not None:
            job.current_page = current_page
        if total_pages is not None:
            job.total_pages = total_pages
        if error_message is not None:
            job.error_message = error_message
        self.jobs[job_id] = self._clone(job)

    def upsert_pages(self, pages: Iterable[PageRecord]) -> None:
        for page in pages:
            self.pages[page.id] = self._clone(page)

    def upsert_sections(self, sections: Iterable[SectionRecord]) -> None:
        for section in sections:
            self.sections[section.id] = self._clone(section)

    def upsert_blocks(self, blocks: Iterable[BlockRecord]) -> None:
        for block in blocks:
            self.blocks[block.id] = self._clone(block)

    def upsert_assets(self, assets: Iterable[AssetRecord]) -> None:
        for asset in assets:
            self.assets[asset.id] = self._clone(asset)

    def list_blocks_for_book(self, book_id: str) -> List[BlockRecord]:
        return [self._clone(b) for b in self.blocks.values() if b.book_id == book_id]


class SqlAlchemyParsingRepository(ParsingRepository):
    """
    SQL-backed repository using SQLAlchemy. Works with SQLite/Postgres URLs.
    """

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    def _session(self) -> Session:
        return self.SessionLocal()

    # region Book operations
    def get_book(self, book_id: str) -> Optional[BookRecord]:
        with self._session() as session:
            model = session.get(BookModel, book_id)
            if not model:
                return None
            return BookRecord(
                id=model.id,
                user_id=model.user_id,
                file_md5=model.file_md5,
                title=model.title,
                author=model.author,
                source=model.source,
                original_file_path=model.original_file_path,
                language=model.language,
                parse_version=model.parse_version,
                status=model.status,
                page_count=model.page_count,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )

    def save_book(self, book: BookRecord) -> None:
        with self._session() as session:
            model = BookModel(
                id=book.id,
                user_id=book.user_id,
                file_md5=book.file_md5,
                title=book.title,
                author=book.author,
                source=book.source,
                original_file_path=book.original_file_path,
                language=book.language,
                parse_version=book.parse_version,
                status=book.status,
                page_count=book.page_count,
                created_at=book.created_at,
                updated_at=book.updated_at,
            )
            session.merge(model)
            session.commit()

    def update_book_status(self, book_id: str, status: BookStatus, page_count: Optional[int] = None) -> None:
        with self._session() as session:
            stmt = update(BookModel).where(BookModel.id == book_id).values(status=status)
            if page_count is not None:
                stmt = stmt.values(page_count=page_count)
            session.execute(stmt)
            session.commit()

    # endregion

    # region Job operations
    def get_job(self, job_id: str) -> Optional[ParseJobRecord]:
        with self._session() as session:
            model = session.get(ParseJobModel, job_id)
            if not model:
                return None
            return ParseJobRecord(
                id=model.id,
                book_id=model.book_id,
                state=model.state,
                phase=model.phase,
                current_page=int(model.current_page or 0),
                total_pages=int(model.total_pages or 0) if model.total_pages else None,
                error_message=model.error_message,
                started_at=model.started_at,
                updated_at=model.updated_at,
                config_json=json.loads(model.config_json or "{}"),
            )

    def save_job(self, job: ParseJobRecord) -> None:
        with self._session() as session:
            model = ParseJobModel(
                id=job.id,
                book_id=job.book_id,
                state=job.state,
                phase=job.phase,
                current_page=job.current_page,
                total_pages=job.total_pages,
                error_message=job.error_message,
                started_at=job.started_at,
                updated_at=job.updated_at,
                config_json=json.dumps(job.config_json or {}),
            )
            session.merge(model)
            session.commit()

    def update_job_state_phase(
        self,
        job_id: str,
        state: Optional[ParseJobState] = None,
        phase: Optional[ParseJobPhase] = None,
        current_page: Optional[int] = None,
        total_pages: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        with self._session() as session:
            stmt = update(ParseJobModel).where(ParseJobModel.id == job_id)
            values = {}
            if state is not None:
                values["state"] = state
            if phase is not None:
                values["phase"] = phase
            if current_page is not None:
                values["current_page"] = current_page
            if total_pages is not None:
                values["total_pages"] = total_pages
            if error_message is not None:
                values["error_message"] = error_message
            if values:
                session.execute(stmt.values(**values))
                session.commit()

    # endregion

    # region content ingestion
    def upsert_pages(self, pages: Iterable[PageRecord]) -> None:
        with self._session() as session:
            for page in pages:
                model = PageModel(
                    id=page.id,
                    book_id=page.book_id,
                    page_number=page.page_number,
                    width=page.width,
                    height=page.height,
                    render_image_path=page.render_image_path,
                    thumbnail_image_path=page.thumbnail_image_path,
                    parse_status=page.parse_status,
                    created_at=page.created_at,
                    updated_at=page.updated_at,
                )
                session.merge(model)
            session.commit()

    def upsert_sections(self, sections: Iterable[SectionRecord]) -> None:
        with self._session() as session:
            for section in sections:
                model = SectionModel(
                    id=section.id,
                    book_id=section.book_id,
                    parent_section_id=section.parent_section_id,
                    level=section.level,
                    title_text=section.title_text,
                    start_page_number=section.start_page_number,
                    end_page_number=section.end_page_number,
                    order_index=section.order_index,
                    created_at=section.created_at,
                    updated_at=section.updated_at,
                )
                session.merge(model)
            session.commit()

    def upsert_blocks(self, blocks: Iterable[BlockRecord]) -> None:
        with self._session() as session:
            for block in blocks:
                model = BlockModel(
                    id=block.id,
                    book_id=block.book_id,
                    page_id=block.page_id,
                    section_id=block.section_id,
                    block_type=block.block_type,
                    text=block.text,
                    markup=block.markup,
                    bbox_x=block.bbox_x,
                    bbox_y=block.bbox_y,
                    bbox_w=block.bbox_w,
                    bbox_h=block.bbox_h,
                    reading_order=block.reading_order,
                    asset_id=block.asset_id,
                    source_id=block.source_id,
                    created_at=block.created_at,
                    updated_at=block.updated_at,
                )
                session.merge(model)
            session.commit()

    def upsert_assets(self, assets: Iterable[AssetRecord]) -> None:
        with self._session() as session:
            for asset in assets:
                model = AssetModel(
                    id=asset.id,
                    book_id=asset.book_id,
                    page_id=asset.page_id,
                    asset_type=asset.asset_type,
                    file_path=asset.file_path,
                    bbox_x=asset.bbox_x,
                    bbox_y=asset.bbox_y,
                    bbox_w=asset.bbox_w,
                    bbox_h=asset.bbox_h,
                    block_id=asset.block_id,
                    created_at=asset.created_at,
                    updated_at=asset.updated_at,
                )
                session.merge(model)
            session.commit()

    def list_blocks_for_book(self, book_id: str) -> List[BlockRecord]:
        with self._session() as session:
            stmt = select(BlockModel).where(BlockModel.book_id == book_id)
            models = session.execute(stmt).scalars().all()
            return [
                BlockRecord(
                    id=m.id,
                    book_id=m.book_id,
                    page_id=m.page_id,
                    section_id=m.section_id,
                    block_type=m.block_type,
                    text=m.text,
                    markup=m.markup,
                    bbox_x=m.bbox_x,
                    bbox_y=m.bbox_y,
                    bbox_w=m.bbox_w,
                    bbox_h=m.bbox_h,
                    reading_order=int(m.reading_order or 0),
                    asset_id=m.asset_id,
                    source_id=m.source_id,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
                for m in models
            ]

    # endregion
