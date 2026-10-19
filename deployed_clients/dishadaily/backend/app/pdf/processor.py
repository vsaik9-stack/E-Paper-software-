import io
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import pymupdf as fitz
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.newspaper import Issue, Page
from app.storage.keys import (
    build_page_image_key,
    build_page_dzi_key,
    build_page_tile_key,
)
from app.storage.service import storage_service


class PDFProcessingError(Exception):
    """Exception raised during PDF validation or processing."""
    pass


class PDFProcessor:
    """High-performance newspaper PDF processing and multi-resolution rendering engine."""

    @staticmethod
    def validate_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
        """Validate PDF integrity and extract document metadata."""
        if not pdf_bytes or len(pdf_bytes) < 32:
            raise PDFProcessingError("Empty or truncated PDF file.")

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise PDFProcessingError(f"Failed to open PDF document: {str(e)}")

        if doc.is_encrypted:
            doc.close()
            raise PDFProcessingError("Password-protected encrypted PDFs are not supported.")

        page_count = doc.page_count
        if page_count == 0:
            doc.close()
            raise PDFProcessingError("PDF document contains 0 pages.")

        metadata = {
            "page_count": page_count,
            "title": doc.metadata.get("title") or "",
            "author": doc.metadata.get("author") or "",
            "creator": doc.metadata.get("creator") or "",
            "producer": doc.metadata.get("producer") or "",
            "format": doc.metadata.get("format") or "PDF",
            "file_size": len(pdf_bytes),
        }
        doc.close()
        return metadata

    @staticmethod
    def _resize_and_compress(
        pil_image: Image.Image,
        max_dimension: int,
        format_name: str = "WEBP",
        quality: int = 85,
    ) -> Tuple[bytes, int, int]:
        """Scale down PIL Image preserving aspect ratio and compress into WebP."""
        width, height = pil_image.size
        longest_edge = max(width, height)

        if longest_edge > max_dimension:
            scale = max_dimension / longest_edge
            new_width = max(1, int(width * scale))
            new_height = max(1, int(height * scale))
            resized = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            resized = pil_image
            new_width, new_height = width, height

        output = io.BytesIO()
        # Convert RGBA to RGB if saving as JPEG, but WebP supports RGBA natively
        if format_name.upper() == "JPEG" and resized.mode in ("RGBA", "P"):
            resized = resized.convert("RGB")

        save_kwargs = {
            "format": format_name.upper(),
            "quality": quality,
            "optimize": True,
        }
        # WebP maximum compression efficiency & razor-sharp typography (0% quality loss)
        if format_name.upper() == "WEBP":
            save_kwargs["method"] = 6
            save_kwargs["subsampling"] = 0

        resized.save(output, **save_kwargs)
        return output.getvalue(), new_width, new_height

    @staticmethod
    def _generate_deepzoom_pyramid(
        pil_image: Image.Image,
        tile_size: int = 512,
        overlap: int = 1,
        quality: int = 85,
    ) -> Tuple[str, Dict[str, bytes]]:
        """
        Generate Microsoft DeepZoom (DZI) schema and pyramid tiles from high-resolution print image.
        Returns XML manifest string and a mapping of relative tile paths to WebP byte buffers.
        """
        import math

        width, height = pil_image.size
        max_dim = max(width, height)
        num_levels = math.ceil(math.log2(max_dim)) + 1

        dzi_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"\n'
            f'  Format="webp"\n'
            f'  Overlap="{overlap}"\n'
            f'  TileSize="{tile_size}">\n'
            f'  <Size Width="{width}" Height="{height}"/>\n'
            f'</Image>'
        )

        tiles: Dict[str, bytes] = {}
        current_img = pil_image

        for level in range(num_levels - 1, -1, -1):
            scale = 2 ** (level - (num_levels - 1))
            lvl_w = max(1, math.ceil(width * scale))
            lvl_h = max(1, math.ceil(height * scale))

            if current_img.size != (lvl_w, lvl_h):
                current_img = pil_image.resize((lvl_w, lvl_h), Image.Resampling.BILINEAR)

            cols = math.ceil(lvl_w / tile_size)
            rows = math.ceil(lvl_h / tile_size)

            for col in range(cols):
                for row in range(rows):
                    # Bounding box taking overlap into account
                    x_start = max(0, col * tile_size - (overlap if col > 0 else 0))
                    y_start = max(0, row * tile_size - (overlap if row > 0 else 0))
                    x_end = min(lvl_w, (col + 1) * tile_size + (overlap if col < cols - 1 else 0))
                    y_end = min(lvl_h, (row + 1) * tile_size + (overlap if row < rows - 1 else 0))

                    tile_crop = current_img.crop((x_start, y_start, x_end, y_end))
                    tile_buf = io.BytesIO()
                    tile_crop.save(tile_buf, format="WEBP", quality=quality, method=2)
                    tile_path = f"{level}/{col}_{row}.webp"
                    tiles[tile_path] = tile_buf.getvalue()

        return dzi_xml, tiles

    async def render_and_save_page(
        self,
        doc: fitz.Document,
        page_index: int,
        pub_date: date,
        edition_slug: str,
        revision: int,
        db_session: AsyncSession,
        issue_id: str,
        tenant_id: Optional[str] = None,
    ) -> Page:
        try:
            page_number = page_index + 1
            page = doc.load_page(page_index)
            rotation = page.rotation

            # Render page at configured DPI
            dpi = settings.PAGE_RENDER_DPI
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)

            # Auto-normalize CMYK or non-RGB color spaces to standard sRGB
            if pix.colorspace and pix.colorspace.n != 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)

            # Convert fitz pixmap directly to PIL Image without PNG re-encoding
            mode = "RGBA" if pix.alpha else "RGB"
            pil_image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            if mode != "RGB":
                pil_image = pil_image.convert("RGB")
            orig_w, orig_h = pil_image.size
        except Exception as e:
            raise ValueError(f"❌ Corrupt PDF Error on Page {page_index + 1}: Failed to rasterize stream ({str(e)}). Processing stopped so you can re-export the PDF.")

        # 1. Large Reader Image (e.g., max 3200px)
        large_bytes, l_w, l_h = self._resize_and_compress(
            pil_image,
            settings.PAGE_LARGE_MAX_DIMENSION,
            format_name=settings.PAGE_IMAGE_FORMAT,
            quality=settings.PAGE_IMAGE_QUALITY,
        )
        large_key = build_page_image_key(
            pub_date, edition_slug, page_number, variant="large", extension="webp", revision=revision, tenant_id=tenant_id
        )
        await storage_service.save_asset(
            storage_key=large_key,
            data=large_bytes,
            asset_type="PAGE_LARGE",
            mime_type="image/webp",
            dimensions=(l_w, l_h),
            db_session=db_session,
            tenant_id=tenant_id,
        )

        # 2. Medium Mobile Image (e.g., max 1600px)
        medium_bytes, m_w, m_h = self._resize_and_compress(
            pil_image,
            settings.PAGE_MEDIUM_MAX_DIMENSION,
            format_name=settings.PAGE_IMAGE_FORMAT,
            quality=settings.PAGE_IMAGE_QUALITY,
        )
        medium_key = build_page_image_key(
            pub_date, edition_slug, page_number, variant="medium", extension="webp", revision=revision, tenant_id=tenant_id
        )
        await storage_service.save_asset(
            storage_key=medium_key,
            data=medium_bytes,
            asset_type="PAGE_MEDIUM",
            mime_type="image/webp",
            dimensions=(m_w, m_h),
            db_session=db_session,
            tenant_id=tenant_id,
        )

        # 3. Thumbnail Image (e.g., max 450px)
        thumb_bytes, t_w, t_h = self._resize_and_compress(
            pil_image,
            settings.PAGE_THUMB_MAX_DIMENSION,
            format_name=settings.PAGE_IMAGE_FORMAT,
            quality=settings.PAGE_IMAGE_QUALITY,
        )
        thumb_key = build_page_image_key(
            pub_date, edition_slug, page_number, variant="thumb", extension="webp", revision=revision, tenant_id=tenant_id
        )
        await storage_service.save_asset(
            storage_key=thumb_key,
            data=thumb_bytes,
            asset_type="PAGE_THUMB",
            mime_type="image/webp",
            dimensions=(t_w, t_h),
            db_session=db_session,
            tenant_id=tenant_id,
        )

        # 4. Ultra-Sharp DeepZoom Pyramid Tiles (OpenSeadragon / Readwhere Standard)
        dzi_xml, tiles = self._generate_deepzoom_pyramid(
            pil_image,
            tile_size=512,
            overlap=1,
            quality=settings.PAGE_IMAGE_QUALITY,
        )
        dzi_manifest_key = build_page_dzi_key(
            pub_date, edition_slug, page_number, revision=revision, tenant_id=tenant_id
        )
        await storage_service.save_asset(
            storage_key=dzi_manifest_key,
            data=dzi_xml.encode("utf-8"),
            asset_type="PAGE_DZI",
            mime_type="application/xml",
            db_session=db_session,
            tenant_id=tenant_id,
        )

        # Batch-save tile assets using canonical prefix derived from dzi_manifest_key
        prefix = dzi_manifest_key.removesuffix(".dzi") + "_files"
        for rel_path, tile_bytes in tiles.items():
            t_key = f"{prefix}/{rel_path}"
            await storage_service.driver.save(t_key, tile_bytes, content_type="image/webp")

        # Check if Page record already exists for this issue & page number
        stmt = select(Page).where(
            Page.issue_id == issue_id,
            Page.page_number == page_number,
        )
        res = await db_session.execute(stmt)
        page_record = res.scalar_one_or_none()

        if page_record:
            page_record.tenant_id = tenant_id or page_record.tenant_id
            page_record.original_image_key = large_key
            page_record.large_image_key = large_key
            page_record.medium_image_key = medium_key
            page_record.thumbnail_image_key = thumb_key
            page_record.dzi_key = dzi_manifest_key
            page_record.width = orig_w
            page_record.height = orig_h
            page_record.dpi = dpi
            page_record.rotation = rotation
            page_record.processing_status = "COMPLETED"
            page_record.display_order = page_number
            page_record.is_deleted = False
        else:
            page_record = Page(
                tenant_id=tenant_id,
                issue_id=issue_id,
                page_number=page_number,
                original_image_key=large_key,
                large_image_key=large_key,
                medium_image_key=medium_key,
                thumbnail_image_key=thumb_key,
                dzi_key=dzi_manifest_key,
                width=orig_w,
                height=orig_h,
                dpi=dpi,
                rotation=rotation,
                processing_status="COMPLETED",
                ocr_status="PENDING",
                article_count=0,
                display_order=page_number,
            )
            db_session.add(page_record)

        await db_session.flush()
        return page_record

    async def process_issue_pdf(
        self,
        pdf_bytes: bytes,
        issue: Issue,
        edition_slug: str,
        db_session: AsyncSession,
        progress_callback: Optional[Any] = None,
    ) -> List[Page]:
        """
        Complete processing pipeline for an issue PDF:
        Validates, extracts metadata, renders all pages at configurable DPIs, and persists assets.
        """
        meta = self.validate_pdf(pdf_bytes)
        issue.page_count = meta["page_count"]
        issue.pdf_file_size = meta["file_size"]
        issue.status = "PROCESSING"
        await db_session.flush()

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages: List[Page] = []

        total_pages = doc.page_count
        for i in range(total_pages):
            page_rec = await self.render_and_save_page(
                doc=doc,
                page_index=i,
                pub_date=issue.publication_date,
                edition_slug=edition_slug,
                revision=issue.revision,
                db_session=db_session,
                issue_id=issue.id,
                tenant_id=issue.tenant_id,
            )
            pages.append(page_rec)

            if progress_callback:
                progress = round(((i + 1) / total_pages) * 100.0, 1)
                await progress_callback(progress, f"Rendered Page {i + 1} of {total_pages} (300 DPI Vector clarity)")

        doc.close()

        # Automatically publish issue live to readers upon 1-click upload completion
        issue.status = "PUBLISHED"
        issue.published_at = datetime.now(timezone.utc)
        await db_session.flush()
        return pages

    @staticmethod
    def render_pdf_crop(
        pdf_bytes: bytes,
        page_number: int,
        normalized_bbox: Dict[str, float],  # {"x": 0.1, "y": 0.2, "width": 0.4, "height": 0.3}
        target_dpi: int = 300,
    ) -> bytes:
        """
        Render a high-DPI crop directly from the vector source PDF for razor-sharp clipping.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_number < 1 or page_number > doc.page_count:
            doc.close()
            raise PDFProcessingError(f"Page {page_number} out of bounds.")

        page = doc.load_page(page_number - 1)
        rect = page.rect  # Total PDF page points (72 points = 1 inch)
        pw, ph = rect.width, rect.height

        # Calculate clip rect in PDF coordinate space points
        rx0 = normalized_bbox["x"] * pw
        ry0 = normalized_bbox["y"] * ph
        rx1 = (normalized_bbox["x"] + normalized_bbox["width"]) * pw
        ry1 = (normalized_bbox["y"] + normalized_bbox["height"]) * ph
        clip_rect = fitz.Rect(rx0, ry0, rx1, ry1)

        # Render at target DPI
        zoom = target_dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, clip=clip_rect, alpha=False)
        output_png = pix.tobytes("png")
        doc.close()
        return output_png


pdf_processor = PDFProcessor()
