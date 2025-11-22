from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class BookStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PAUSED = "paused"
    PARSED = "parsed"
    FAILED = "failed"
    NEEDS_REPARSE = "needs_reparse"


class ParseJobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ParseJobPhase(str, Enum):
    PRECHECK = "precheck"
    DOCLING_PARSE = "docling_parse"
    DB_INGESTION = "db_ingestion"
    INDEXING = "indexing"


@dataclass
class BBox:
    x: float
    y: float
    w: float
    h: float


@dataclass
class ParsedPage:
    page_number: int
    width: float
    height: float


@dataclass
class ParsedSection:
    id: str
    parent_id: Optional[str]
    level: int
    title_text: str
    start_page_number: int
    end_page_number: int
    order_index: int


@dataclass
class ParsedBlock:
    id: str
    page_number: int
    block_type: str
    text: str
    bbox: BBox
    reading_order: int
    section_path: List[str] = field(default_factory=list)
    markup: Optional[str] = None
    asset_id: Optional[str] = None
    source_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedAsset:
    id: str
    page_number: int
    asset_type: str
    bbox: BBox
    image_bytes: Optional[bytes] = None
    image_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedBook:
    pages: List[ParsedPage]
    sections: List[ParsedSection]
    blocks: List[ParsedBlock]
    assets: List[ParsedAsset]
    engine_version: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BookRecord:
    id: str
    user_id: str
    file_md5: str
    title: str
    author: Optional[str]
    source: str
    original_file_path: str
    language: str
    parse_version: str
    status: BookStatus = BookStatus.UPLOADED
    page_count: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ParseJobRecord:
    id: str
    book_id: str
    state: ParseJobState
    phase: ParseJobPhase
    current_page: int = 0
    total_pages: Optional[int] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=datetime.utcnow)
    config_json: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PageRecord:
    id: str
    book_id: str
    page_number: int
    width: float
    height: float
    render_image_path: Optional[str]
    thumbnail_image_path: Optional[str]
    parse_status: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SectionRecord:
    id: str
    book_id: str
    parent_section_id: Optional[str]
    level: int
    title_text: str
    start_page_number: int
    end_page_number: int
    order_index: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BlockRecord:
    id: str
    book_id: str
    page_id: str
    section_id: Optional[str]
    block_type: str
    text: str
    markup: Optional[str]
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    reading_order: int
    asset_id: Optional[str]
    source_id: Optional[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AssetRecord:
    id: str
    book_id: str
    page_id: str
    asset_type: str
    file_path: str
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    block_id: Optional[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

