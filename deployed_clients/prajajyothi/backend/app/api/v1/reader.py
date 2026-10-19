from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.tenant import resolve_current_tenant
from app.models.newspaper import ArticleRegion, Edition, Issue, Page
from app.models.tenant import Tenant
from app.schemas.epaper import (
    ArchiveDateItem,
    ArticleRegionOut,
    IssueReaderOut,
    PageOut,
)
from app.storage.service import storage_service

router = APIRouter(prefix="/reader", tags=["White-Label Newspaper Reader"])


def _serialize_issue_for_reader(issue: Issue, edition: Edition) -> IssueReaderOut:
    pages_out: List[PageOut] = []
    sorted_pages = sorted(
        [p for p in issue.pages if not p.is_deleted],
        key=lambda x: x.page_number,
    )
    for p in sorted_pages:
        articles_out = [
            ArticleRegionOut(
                id=a.id,
                page_id=a.page_id,
                title=a.title,
                coordinates=a.coordinates,
                content_text=a.content_text,
                clip_url=storage_service.resolve_url(a.clip_image_key),
            )
            for a in (p.articles or [])
        ]
        pages_out.append(
            PageOut(
                id=p.id,
                page_number=p.page_number,
                title=p.title or f"Page {p.page_number}",
                width=p.width,
                height=p.height,
                dpi=p.dpi,
                large_url=storage_service.resolve_url(p.large_image_key),
                medium_url=storage_service.resolve_url(p.medium_image_key),
                thumbnail_url=storage_service.resolve_url(p.thumbnail_image_key),
                dzi_url=storage_service.resolve_url(p.dzi_key),
                articles=articles_out,
            )
        )

    return IssueReaderOut(
        id=issue.id,
        tenant_id=issue.tenant_id,
        edition_id=edition.id,
        edition_name=edition.name,
        edition_slug=edition.slug,
        publication_date=issue.publication_date,
        revision=issue.revision,
        page_count=len(pages_out),
        status=issue.status,
        pdf_url=storage_service.resolve_url(issue.pdf_storage_key),
        pages=pages_out,
    )


@router.get("/today", response_model=IssueReaderOut)
async def get_today_issue(
    edition: Optional[str] = Query(None, description="Edition slug"),
    pub_date: Optional[date] = Query(None, description="Optional target date YYYY-MM-DD"),
    tenant: Tenant = Depends(resolve_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns today's (or latest active) published issue for the resolved Tenant and selected Edition,
    including full Deep Zoom (`dzi_url`) and multi-resolution WebP URLs for every page.
    """
    # Resolve target edition for this tenant
    ed_stmt = select(Edition).where(Edition.tenant_id == tenant.id, Edition.is_active == True)
    if edition:
        ed_stmt = ed_stmt.where(Edition.slug == edition.strip().lower())
    else:
        ed_stmt = ed_stmt.order_by(Edition.display_order.asc())

    ed_res = await db.execute(ed_stmt)
    target_edition = ed_res.scalars().first()

    if not target_edition:
        # Fallback to first active edition of tenant if requested slug didn't match
        fallback_ed_stmt = (
            select(Edition)
            .where(Edition.tenant_id == tenant.id, Edition.is_active == True)
            .order_by(Edition.display_order.asc())
        )
        ed_res = await db.execute(fallback_ed_stmt)
        target_edition = ed_res.scalars().first()

    if not target_edition:
        raise HTTPException(status_code=404, detail="No active editions found for this newspaper.")

    # Find issue matching pub_date (or latest published issue for this edition)
    issue_stmt = (
        select(Issue)
        .options(selectinload(Issue.pages).selectinload(Page.articles))
        .where(
            Issue.tenant_id == tenant.id,
            Issue.edition_id == target_edition.id,
            Issue.status == "PUBLISHED",
        )
    )
    if pub_date:
        issue_stmt = issue_stmt.where(Issue.publication_date == pub_date)

    issue_stmt = issue_stmt.order_by(desc(Issue.publication_date), desc(Issue.revision))
    issue_res = await db.execute(issue_stmt)
    issue = issue_res.scalars().first()

    # If no issue for specific edition or date, fallback to latest published issue across the tenant
    if not issue and not pub_date:
        any_issue_stmt = (
            select(Issue)
            .options(selectinload(Issue.pages).selectinload(Page.articles), selectinload(Issue.edition))
            .where(Issue.tenant_id == tenant.id, Issue.status == "PUBLISHED")
            .order_by(desc(Issue.publication_date), desc(Issue.revision))
        )
        any_res = await db.execute(any_issue_stmt)
        issue = any_res.scalars().first()
        if issue and issue.edition:
            target_edition = issue.edition

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="No published issue found for the selected edition and date.",
        )

    issue.views_count = (issue.views_count or 0) + 1
    await db.flush()

    return _serialize_issue_for_reader(issue, target_edition)


@router.get("/issue/{issue_id}", response_model=IssueReaderOut)
async def get_issue_by_id(
    issue_id: str,
    tenant: Tenant = Depends(resolve_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Returns a specific issue by ID (strictly isolated to the current tenant)."""
    stmt = (
        select(Issue)
        .options(
            selectinload(Issue.pages).selectinload(Page.articles),
            selectinload(Issue.edition),
        )
        .where(Issue.id == issue_id, Issue.tenant_id == tenant.id)
    )
    res = await db.execute(stmt)
    issue = res.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found for this newspaper tenant.")

    issue.views_count = (issue.views_count or 0) + 1
    await db.flush()

    return _serialize_issue_for_reader(issue, issue.edition)


@router.get("/archive", response_model=List[ArchiveDateItem])
async def get_archive_calendar(
    edition: Optional[str] = Query(None, description="Optional edition slug filter"),
    tenant: Tenant = Depends(resolve_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Returns calendar dates with available published issues for the resolved tenant."""
    stmt = (
        select(Issue)
        .options(selectinload(Issue.edition), selectinload(Issue.pages))
        .where(Issue.tenant_id == tenant.id, Issue.status == "PUBLISHED")
        .order_by(desc(Issue.publication_date), desc(Issue.revision))
    )
    res = await db.execute(stmt)
    issues = res.scalars().all()

    items: List[ArchiveDateItem] = []
    for iss in issues:
        if edition and iss.edition and iss.edition.slug != edition.strip().lower():
            continue
        first_page_thumb = None
        if iss.pages:
            sorted_p = sorted(iss.pages, key=lambda x: x.page_number)
            first_page_thumb = storage_service.resolve_url(sorted_p[0].thumbnail_image_key)

        items.append(
            ArchiveDateItem(
                publication_date=iss.publication_date.isoformat(),
                issue_id=iss.id,
                edition_slug=iss.edition.slug if iss.edition else "main",
                edition_name=iss.edition.name if iss.edition else "Main Edition",
                page_count=iss.page_count,
                thumbnail_url=first_page_thumb,
            )
        )
    return items
