from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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

