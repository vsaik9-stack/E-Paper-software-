import io
import uuid
from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.tenant import resolve_current_tenant
from app.models.newspaper import Issue, Page
from app.models.tenant import Tenant
from app.pdf.clip_generator import clip_generator
from app.pdf.processor import pdf_processor
from app.schemas.epaper import ClipCropRequest, ClipCropResponse
from app.storage.keys import build_clip_key
from app.storage.service import storage_service

router = APIRouter(prefix="/clipping", tags=["White-Label Article Clipping Engine"])


@router.post("/crop", response_model=ClipCropResponse)
async def create_white_label_clip(
    payload: ClipCropRequest,
    tenant: Tenant = Depends(resolve_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a White-Labeled newspaper clipping image with the Tenant's logo/masthead banner,
    brand colors, publication date, edition badge, and copyright strip.
    """
    stmt = (
        select(Issue)
        .options(selectinload(Issue.edition), selectinload(Issue.pages))
        .where(Issue.id == payload.issue_id, Issue.tenant_id == tenant.id)
    )
    res = await db.execute(stmt)
    issue = res.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found for this newspaper tenant.")

    target_page: Page | None = None
    for p in issue.pages:
        if p.page_number == payload.page_number:
            target_page = p
            break

    if not target_page:
        raise HTTPException(status_code=404, detail=f"Page {payload.page_number} not found.")

    bbox = {
        "x": payload.x,
        "y": payload.y,
        "width": payload.width,
        "height": payload.height,
    }

    crop_bytes: bytes | None = None

    # 1. Try high-DPI vector crop directly from source PDF if stored
    if issue.pdf_storage_key:
        pdf_bytes = await storage_service.get_data(issue.pdf_storage_key)
        if pdf_bytes:
            try:
                crop_bytes = pdf_processor.render_pdf_crop(
                    pdf_bytes=pdf_bytes,
                    page_number=payload.page_number,
                    normalized_bbox=bbox,
                    target_dpi=300,
                )
            except Exception:
                crop_bytes = None

    # 2. Fallback to cropping from the high-resolution large WebP page image
    if not crop_bytes and target_page.large_image_key:
        large_bytes = await storage_service.get_data(target_page.large_image_key)
        if large_bytes:
            img = Image.open(io.BytesIO(large_bytes)).convert("RGB")
            iw, ih = img.size
            cx0 = int(bbox["x"] * iw)
            cy0 = int(bbox["y"] * ih)
            cx1 = int((bbox["x"] + bbox["width"]) * iw)
            cy1 = int((bbox["y"] + bbox["height"]) * ih)
            cropped = img.crop((cx0, cy0, max(cx0 + 10, cx1), max(cy0 + 10, cy1)))
            buf = io.BytesIO()
            cropped.save(buf, format="PNG")
            crop_bytes = buf.getvalue()

    if not crop_bytes:
        raise HTTPException(status_code=500, detail="Unable to load source page assets for clipping.")

    edition_name = issue.edition.name if issue.edition else tenant.name
    pub_date_str = issue.publication_date.strftime("%d-%b-%Y")

    # Composite with White-Label Tenant Branding
    branded_jpeg_bytes = clip_generator.create_branded_clip(
        crop_image_bytes=crop_bytes,
        edition_name=edition_name,
        pub_date=pub_date_str,
        page_number=payload.page_number,
        headline=payload.headline,
        tenant_name=tenant.name,
        tenant_primary_color=tenant.brand_primary_color,
        tenant_secondary_color=tenant.brand_secondary_color,
        tenant_copyright=tenant.copyright_text,
    )

    clip_id = str(uuid.uuid4())[:12]
    clip_storage_key = build_clip_key(
        article_id=clip_id,
        variant="high_res",
        extension="jpg",
        tenant_id=tenant.id,
    )

    await storage_service.save_asset(
        storage_key=clip_storage_key,
        data=branded_jpeg_bytes,
        asset_type="ARTICLE_CLIP",
        mime_type="image/jpeg",
        db_session=db,
        tenant_id=tenant.id,
    )

    clip_url = storage_service.resolve_url(clip_storage_key) or ""
    share_text = (
        f"📰 *{tenant.name}* ({edition_name} • {pub_date_str} • Page {payload.page_number})\n"
        f"Read full digital edition online!"
    )

    return ClipCropResponse(
        clip_id=clip_id,
        clip_url=clip_url,
        share_text=share_text,
        tenant_name=tenant.name,
        edition_name=edition_name,
        publication_date=pub_date_str,
        page_number=payload.page_number,
    )
