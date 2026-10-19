import hashlib
import mimetypes
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from app.storage.local import LocalStorageDriver
from app.storage.service import storage_service

router = APIRouter(prefix="/assets", tags=["Storage Assets Delivery"])


@router.api_route("/{storage_key:path}", methods=["GET", "HEAD"])
async def serve_storage_asset(storage_key: str, request: Request) -> Response:
    """Validate local assets from metadata and stream instead of buffering full files."""
    # Published newspaper page assets contain revision keys (rev_1, rev_2) and are permanent & immutable.
    # We instruct Cloudflare and browsers to cache them at the edge for 1 year without round-trip revalidation.
    is_page_asset = (
        "pages/p_" in storage_key
        or "clips/" in storage_key
        or storage_key.endswith(".webp")
        or storage_key.endswith(".dzi")
    )
    cache_control = (
        "public, max-age=31536000, immutable"
        if is_page_asset
        else "public, max-age=3600, must-revalidate"
    )
    headers = {
        "Cache-Control": cache_control,
        "X-Content-Type-Options": "nosniff",
        "Access-Control-Allow-Origin": "*",
    }
    if storage_key.endswith(".webp"):
        mime_type = "image/webp"
    elif storage_key.endswith(".dzi") or storage_key.endswith(".xml"):
        mime_type = "application/xml"
    elif storage_key.endswith(".pdf"):
        mime_type = "application/pdf"
    else:
        mime_type = mimetypes.guess_type(storage_key)[0] or "application/octet-stream"
    if isinstance(storage_service.driver, LocalStorageDriver):
        root = Path(storage_service.driver.base_dir).resolve()
        path = (root / storage_key).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(status_code=404, detail="Asset not found.")
        stat = await run_in_threadpool(path.stat)
        etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
        headers["ETag"] = etag
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return FileResponse(path, media_type=mime_type, headers=headers, stat_result=stat)

    data = await storage_service.get_data(storage_key)
    if data is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    headers["ETag"] = f'"{hashlib.sha256(data).hexdigest()}"'
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    headers["Content-Length"] = str(len(data))
    return Response(content=b"" if request.method == "HEAD" else data, media_type=mime_type, headers=headers)
