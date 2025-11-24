from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import uuid
from io import BytesIO

from .models import BBox, ParsedAsset, ParsedBlock, ParsedBook, ParsedPage, ParsedSection

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.datamodel.accelerator_options import (
            AcceleratorOptions,
            AcceleratorDevice,
        )
from docling_core.types.doc.document import TextItem, TableItem, PictureItem, SectionHeaderItem
from docling_core.types.doc import BoundingBox as DlBBox

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

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class DoclingParsingEngine(ParsingEngine):
    """
    Docling-based parser (with configurable OCR via Docling's PDF pipeline).

    Requires the `docling` package and its dependencies to be installed.
    Uses Docling's `DocumentConverter` with `PdfPipelineOptions` and maps the
    resulting DoclingDocument into the internal dataclasses.
    """
    #  backend=PyPdfiumDocumentBackend 
    # known bug: default backend failed to parse some pdfs with non-standard size #2536
    def __init__(self, perform_ocr: bool = True, engine_version: str = "docling-latest"):
        
        
        accelerator_options = AcceleratorOptions(
            num_threads=8, device=AcceleratorDevice.AUTO
        )

        self.engine_version = engine_version

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = perform_ocr

        # These are generally useful defaults for rich layout understanding.
        pipeline_options.do_table_structure = True
        pipeline_options.generate_picture_images = True
        pipeline_options.generate_page_images = True
        pipeline_options.images_scale = 2.0
        # use rapidocr 
        pipeline_options.ocr_options = RapidOcrOptions()
        pipeline_options.accelerator_options  = accelerator_options
        
        
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )

    def parse(self, pdf_path: Path) -> ParsedBook:
        try:
            result = self.converter.convert(pdf_path)
        
            doc = result.document
        except Exception:
            raise RuntimeError("parsing failed")
 

        
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

    def _map_docling_document(self, doc):
        generated_ids = {}

        def ensure_id(obj):
            obj_id = getattr(obj, "id", None)
            if obj_id:
                return str(obj_id)
            key = id(obj)
            if key not in generated_ids:
                generated_ids[key] = str(uuid.uuid4())
            return generated_ids[key]

        pages = []
        page_heights = {}
        for page_no, page in doc.pages.items():            # 1-based keys
            size = page.size or type("S",(object,),{"width":0,"height":0})()
            page_heights[page_no] = getattr(size, "height", None)
            pages.append(ParsedPage(page_number=page_no, width=size.width, height=size.height))

        blocks = []
        for item, level in doc.iterate_items(traverse_pictures=True):
            prov = item.prov[0] if getattr(item, "prov", []) else None
            if not prov or prov.page_no is None or prov.bbox is None:
                continue  # drop incomplete provenance to avoid None downstream
            page_height = page_heights.get(prov.page_no)
            bbox = self._coerce_bbox(prov.bbox, page_height=page_height)
            if bbox is None:
                continue
            text = getattr(item, "text", "")
            label = getattr(item, "label", "text")
            item_id = ensure_id(item)
            asset_id = item_id if isinstance(item, (PictureItem, TableItem)) else None
            blocks.append(
                ParsedBlock(
                    id=item_id,
                    page_number=prov.page_no,
                    block_type=str(label),
                    text=text,
                    markup=None,
                    bbox=bbox,
                    reading_order=len(blocks),           # iterate_items is in reading order
                    section_path=[],
                    asset_id=asset_id,
                    source_id=item_id,
                    metadata=getattr(item, "metadata", {}),
                )
            )

        sections = []
        order = 0
        for item, level in doc.iterate_items():
            if isinstance(item, SectionHeaderItem):
                prov = item.prov[0] if item.prov else None
                if not prov or prov.page_no is None:
                    continue
                sections.append(
                    ParsedSection(
                        id=str(getattr(item, "id", order)),
                        parent_id=None,                  # derive from body tree if needed
                        level=level,                     # tree depth
                        title_text=item.text,
                        start_page_number=prov.page_no,
                        end_page_number=prov.page_no,
                        order_index=order,
                    )
                )
                order += 1

        assets = []
        for pic in doc.pictures:
            prov = pic.prov[0] if pic.prov else None
            if not prov or prov.page_no is None or prov.bbox is None:
                continue
            page_height = page_heights.get(prov.page_no)
            bbox = self._coerce_bbox(prov.bbox, page_height=page_height)
            if bbox is None:
                continue
            img = pic.get_image(doc)  # PIL.Image or None if images weren’t generated
            asset_id = ensure_id(pic)
            image_bytes = self._image_to_png_bytes(img)

            assets.append(
                ParsedAsset(
                    id=asset_id,
                    page_number=prov.page_no,
                    asset_type="picture",
                    bbox=bbox,
                    image_bytes=image_bytes,
                    image_path=None,
                    metadata=getattr(pic, "metadata", {}),
                )
            )
        for table in doc.tables:
            prov = table.prov[0] if table.prov else None
            if not prov or prov.page_no is None or prov.bbox is None:
                continue
            page_height = page_heights.get(prov.page_no)
            bbox = self._coerce_bbox(prov.bbox, page_height=page_height)
            if bbox is None:
                continue
            img = table.get_image(doc)
            asset_id = ensure_id(table)
            image_bytes = self._image_to_png_bytes(img)
            assets.append(
                ParsedAsset(
                    id=asset_id,
                    page_number=prov.page_no,
                    asset_type="table",
                    bbox=bbox,
                    image_bytes=image_bytes,
                    image_path=None,
                    metadata=getattr(table, "metadata", {}),
                )
            )

        return pages, sections, blocks, assets

    def _coerce_bbox(self, bbox_obj, page_height: float | None = None) -> Optional[BBox]:
        if bbox_obj is None:
            return None

        # Docling native BoundingBox
        if isinstance(bbox_obj, DlBBox):
            bb = bbox_obj
            # convert to top-left if caller provides page height and origin is bottom-left
            if page_height is not None and bb.coord_origin.name == "BOTTOMLEFT":
                bb = bb.to_top_left_origin(page_height=page_height)
            return BBox(x=bb.l, y=bb.t, w=bb.width, h=bb.height)

        # Already top-left/width/height style
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


    def _image_to_png_bytes(self, image) -> Optional[bytes]:
        if image is None:
            return None
        buffer = BytesIO()
        try:
            image.save(buffer, format="PNG")
        except Exception:
            return None
        return buffer.getvalue()


# TODO: save pages' images 