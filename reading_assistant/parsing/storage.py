from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class StoragePaths:
    root: Path

    def book_dir(self, book_id: str) -> Path:
        return self.root / "books" / str(book_id)

    def original_pdf_path(self, book_id: str) -> Path:
        return self.book_dir(book_id) / "original.pdf"

    def docling_output_path(self, book_id: str) -> Path:
        return self.book_dir(book_id) / "docling_output.json"

    def page_image_path(self, book_id: str, page_number: int) -> Path:
        return self.book_dir(book_id) / "pages" / f"{page_number}.png"

    def page_thumbnail_path(self, book_id: str, page_number: int) -> Path:
        return self.book_dir(book_id) / "pages" / f"{page_number}_thumb.png"

    def page_pdf_path(self, book_id: str, page_number: int) -> Path:
        return self.book_dir(book_id) / "pages" / f"{page_number}.pdf"

    def asset_path(self, book_id: str, asset_id: str) -> Path:
        return self.book_dir(book_id) / "assets" / f"{asset_id}.png"


class LocalBookStorage:
    """
    Manages filesystem layout for books, parser outputs, and assets.
    """

    def __init__(self, storage_paths: StoragePaths):
        self.paths = storage_paths

    def ensure_base_dirs(self, book_id: str) -> None:
        base = self.paths.book_dir(book_id)
        (base / "pages").mkdir(parents=True, exist_ok=True)
        (base / "assets").mkdir(parents=True, exist_ok=True)

    def save_original_pdf(self, book_id: str, source_pdf: Path) -> Path:
        self.ensure_base_dirs(book_id)
        target = self.paths.original_pdf_path(book_id)
        shutil.copy2(source_pdf, target)
        return target

    def write_docling_output(self, book_id: str, parsed_book_json: dict) -> Path:
        self.ensure_base_dirs(book_id)
        target = self.paths.docling_output_path(book_id)
        with target.open("w", encoding="utf-8") as f:
            json.dump(parsed_book_json, f, ensure_ascii=False, indent=2)
        return target

    def write_asset_image(self, book_id: str, asset_id: str, data: bytes) -> Path:
        self.ensure_base_dirs(book_id)
        target = self.paths.asset_path(book_id, asset_id)
        target.write_bytes(data)
        return target

    def page_image_exists(self, book_id: str, page_number: int) -> bool:
        return self.paths.page_image_path(book_id, page_number).exists()

    def asset_exists(self, book_id: str, asset_id: str) -> bool:
        return self.paths.asset_path(book_id, asset_id).exists()

    def find_original_pdf(self, book_id: str) -> Optional[Path]:
        path = self.paths.original_pdf_path(book_id)
        return path if path.exists() else None

    def render_pdf_pages(
        self,
        book_id: str,
        pdf_path: Path,
        dpi: int = 150,
        render_thumbnails: bool = True,
        thumbnail_scale: float = 0.3,
        write_page_pdfs: bool = True,
    ) -> Dict[int, Dict[str, Optional[Path]]]:
        """
        Pre-render each page to an image (and optional thumbnail + single-page PDF) once.
        Returns a mapping of page_number -> artifact paths and page size.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("PyMuPDF is required for page rendering. Please install 'pymupdf'.") from exc

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found for rendering: {pdf_path}")

        self.ensure_base_dirs(book_id)
        artifacts: Dict[int, Dict[str, Optional[Path]]] = {}

        doc = fitz.open(pdf_path)
        try:
            total_pages = doc.page_count
            if total_pages == 0:
                raise ValueError(f"PDF has zero pages: {pdf_path}")

            scale = dpi / 72.0
            thumb_scale_val = scale * thumbnail_scale
            for idx in range(total_pages):
                page_number = idx + 1
                page = doc.load_page(idx)

                # Full-resolution image
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
                img_path = self.paths.page_image_path(book_id, page_number)
                img_path.parent.mkdir(parents=True, exist_ok=True)
                pix.save(img_path)

                thumb_path: Optional[Path] = None
                if render_thumbnails:
                    thumb_pix = page.get_pixmap(matrix=fitz.Matrix(thumb_scale_val, thumb_scale_val))
                    thumb_path = self.paths.page_thumbnail_path(book_id, page_number)
                    thumb_pix.save(thumb_path)

                page_pdf_path: Optional[Path] = None
                if write_page_pdfs:
                    single = fitz.open()
                    single.insert_pdf(doc, from_page=idx, to_page=idx)
                    page_pdf_path = self.paths.page_pdf_path(book_id, page_number)
                    page_pdf_path.parent.mkdir(parents=True, exist_ok=True)
                    single.save(page_pdf_path)
                    single.close()

                artifacts[page_number] = {
                    "image": img_path,
                    "thumbnail": thumb_path,
                    "pdf": page_pdf_path,
                }
        finally:
            doc.close()

        # Validate coverage
        missing_pages = [p for p in range(1, total_pages + 1) if p not in artifacts]
        if missing_pages:
            raise RuntimeError(f"Failed to render pages {missing_pages} for book {book_id}")
        for page_num, files in artifacts.items():
            if not files.get("image"):
                raise RuntimeError(f"Missing rendered image for book {book_id} page {page_num}")
            if render_thumbnails and files.get("thumbnail") is None:
                logger.warning("Thumbnail missing for book %s page %s", book_id, page_num)
            if write_page_pdfs and files.get("pdf") is None:
                logger.warning("Single-page PDF missing for book %s page %s", book_id, page_num)
        return artifacts

