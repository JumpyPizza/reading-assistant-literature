from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import uuid

from .models import BBox, ParsedAsset, ParsedBlock, ParsedBook, ParsedPage, ParsedSection


class ParsingEngine:
    """
    Abstract parsing engine. Implementations should be stateless and reusable.
    """

    def parse(self, pdf_path: Path) -> ParsedBook:
        raise NotImplementedError

    def count_pages(self, pdf_path: Path) -> Optional[int]:
        """
        Optional lightweight page counter. Return None if not supported.
        """
        return None


class DoclingParsingEngine(ParsingEngine):
    """
    Docling + RapidOCR based parser. Requires the `docling` package and its
    dependencies to be installed. It uses docling's `DocumentConverter` API
    and maps resulting objects to the internal dataclasses.
    """

    def __init__(self, perform_ocr: bool = True, engine_version: str = "docling-latest"):
        from docling.document_converter import (
            DocumentConversionParams,
            DocumentConverter,
            PdfFormatOption,
        )
        from docling.models.docling_models import PageModelType

        self.engine_version = engine_version
        format_options = {
            ".pdf": PdfFormatOption(
                perform_ocr=perform_ocr,
                pdf_page_model=PageModelType.DETECTED_LAYOUT,
            )
        }
        self.converter = DocumentConverter(
            conversion_params=DocumentConversionParams(format_options=format_options)
        )

    def parse(self, pdf_path: Path) -> ParsedBook:
        result = self.converter.convert(str(pdf_path))
        doc = result.document
        pages, sections, blocks, assets = self._map_docling_document(doc)
        return ParsedBook(
            pages=pages,
            sections=sections,
            blocks=blocks,
            assets=assets,
            engine_version=self.engine_version,
            metadata=getattr(result, "metadata", {}) if hasattr(result, "metadata") else {},
        )

    def count_pages(self, pdf_path: Path) -> Optional[int]:
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(pdf_path))
            return len(reader.pages)
        except Exception:
            return None

    def _map_docling_document(self, doc) -> (List[ParsedPage], List[ParsedSection], List[ParsedBlock], List[ParsedAsset]):
        pages: List[ParsedPage] = []
        sections: List[ParsedSection] = []
        blocks: List[ParsedBlock] = []
        assets: List[ParsedAsset] = []

        raw_pages = getattr(doc, "pages", [])
        for idx, page in enumerate(raw_pages):
            page_number = getattr(page, "page_number", getattr(page, "number", idx + 1))
            width = getattr(page, "width", getattr(page, "size", [0, 0])[0] if hasattr(page, "size") else 0)
            height = getattr(page, "height", getattr(page, "size", [0, 0])[1] if hasattr(page, "size") else 0)
            pages.append(ParsedPage(page_number=page_number, width=width, height=height))

            page_blocks = getattr(page, "blocks", None) or getattr(page, "elements", [])
            for block_idx, block in enumerate(page_blocks):
                bbox = self._coerce_bbox(getattr(block, "bbox", None))
                block_type = getattr(block, "category", getattr(block, "type", "paragraph"))
                text = getattr(block, "text", getattr(block, "content", ""))
                markup = getattr(block, "text_representation", None)
                asset_id = getattr(block, "asset_id", None)
                section_path = []
                blocks.append(
                    ParsedBlock(
                        id=str(getattr(block, "id", f"{page_number}-{block_idx}")),
                        page_number=page_number,
                        block_type=str(block_type),
                        text=text,
                        markup=markup,
                        bbox=bbox or BBox(0, 0, 0, 0),
                        reading_order=getattr(block, "reading_order", block_idx),
                        section_path=section_path,
                        asset_id=str(asset_id) if asset_id else None,
                        source_id=str(getattr(block, "id", None)),
                        metadata=getattr(block, "metadata", {}),
                    )
                )

        raw_sections = getattr(doc, "sections", [])
        for order_idx, section in enumerate(raw_sections):
            sections.append(
                ParsedSection(
                    id=str(getattr(section, "id", order_idx)),
                    parent_id=getattr(section, "parent_id", None),
                    level=getattr(section, "level", 1),
                    title_text=getattr(section, "title", getattr(section, "title_text", "")),
                    start_page_number=getattr(section, "start_page", getattr(section, "start_page_number", 1)),
                    end_page_number=getattr(section, "end_page", getattr(section, "end_page_number", 1)),
                    order_index=order_idx,
                )
            )

        raw_assets = getattr(doc, "assets", [])
        for asset in raw_assets:
            bbox = self._coerce_bbox(getattr(asset, "bbox", None))
            assets.append(
                ParsedAsset(
                    id=str(getattr(asset, "id", "")),
                    page_number=getattr(asset, "page_number", 1),
                    asset_type=str(getattr(asset, "type", getattr(asset, "asset_type", "figure"))),
                    bbox=bbox or BBox(0, 0, 0, 0),
                    image_bytes=getattr(asset, "image_bytes", None),
                    image_path=getattr(asset, "image_path", None),
                    metadata=getattr(asset, "metadata", {}),
                )
            )
        return pages, sections, blocks, assets

    def _coerce_bbox(self, bbox_obj) -> Optional[BBox]:
        if bbox_obj is None:
            return None
        # Support multiple common bbox shapes from docling or PDF boxes.
        if hasattr(bbox_obj, "x") and hasattr(bbox_obj, "y") and hasattr(bbox_obj, "w") and hasattr(bbox_obj, "h"):
            return BBox(x=bbox_obj.x, y=bbox_obj.y, w=bbox_obj.w, h=bbox_obj.h)
        if hasattr(bbox_obj, "left") and hasattr(bbox_obj, "top") and hasattr(bbox_obj, "width") and hasattr(bbox_obj, "height"):
            return BBox(x=bbox_obj.left, y=bbox_obj.top, w=bbox_obj.width, h=bbox_obj.height)
        if hasattr(bbox_obj, "x0") and hasattr(bbox_obj, "y0") and hasattr(bbox_obj, "x1") and hasattr(bbox_obj, "y1"):
            return BBox(x=bbox_obj.x0, y=bbox_obj.y0, w=bbox_obj.x1 - bbox_obj.x0, h=bbox_obj.y1 - bbox_obj.y0)
        if isinstance(bbox_obj, (list, tuple)) and len(bbox_obj) == 4:
            x0, y0, x1, y1 = bbox_obj
            return BBox(x=x0, y=y0, w=x1 - x0, h=y1 - y0)
        return None


class DummyParsingEngine(ParsingEngine):
    """
    Minimal stand-in parser for local development.

    It treats each newline-delimited paragraph in a text file as a block on
    a single synthetic page. This keeps the worker pipeline testable without
    needing Docling or PDF dependencies.
    """

    def __init__(self, engine_version: str = "dummy-0.1"):
        self.engine_version = engine_version

    def parse(self, pdf_path: Path) -> ParsedBook:
        text = pdf_path.read_text(encoding="utf-8")
        blocks = []
        y_cursor = 50.0
        for idx, paragraph in enumerate([p.strip() for p in text.split("\n") if p.strip()]):
            block_id = f"blk-{idx}"
            bbox = BBox(x=50.0, y=y_cursor, w=512.0, h=40.0)
            blocks.append(
                ParsedBlock(
                    id=block_id,
                    page_number=1,
                    block_type="paragraph",
                    text=paragraph,
                    bbox=bbox,
                    reading_order=idx,
                    section_path=[],
                    markup=None,
                    asset_id=None,
                    source_id=block_id,
                )
            )
            y_cursor += 45.0
        page = ParsedPage(page_number=1, width=612.0, height=792.0)
        parsed_book = ParsedBook(
            pages=[page],
            sections=[],
            blocks=blocks,
            assets=[],
            engine_version=self.engine_version,
            metadata={"source": "dummy_text"},
        )
        return parsed_book

    def count_pages(self, pdf_path: Path) -> Optional[int]:
        return 1


def generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
