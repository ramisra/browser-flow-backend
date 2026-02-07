"""File download endpoints."""

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/files", tags=["files"])


async def get_user_guest_id(
    x_user_guest_id: Optional[str] = Header(None, alias="X-User-Guest-ID"),
) -> uuid.UUID:
    """Extract and validate user_guest_id from header."""
    if not x_user_guest_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Guest-ID header is required",
        )

    try:
        return uuid.UUID(x_user_guest_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user_guest_id format: {x_user_guest_id}",
        )


def _resolve_excel_path(file_path: str, storage_root: Path) -> Path:
    if not file_path or not file_path.strip():
        raise HTTPException(status_code=400, detail="File path is required")

    if file_path.startswith(("/", "\\")) or "\\" in file_path:
        raise HTTPException(status_code=400, detail="Invalid file path")

    parts = Path(file_path).parts
    if ".." in parts:
        raise HTTPException(status_code=400, detail="Invalid file path")

    resolved_root = storage_root.resolve()
    resolved_path = (resolved_root / file_path).resolve()

    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        raise HTTPException(status_code=404, detail="Excel file not found")

    return resolved_path


@router.get("/excel/{file_path:path}")
async def download_excel_file(
    file_path: str,
    user_guest_id: uuid.UUID = Depends(get_user_guest_id),
):
    """Download an Excel file by relative path."""
    storage_root = Path("app/storage/excel")
    resolved_path = _resolve_excel_path(file_path, storage_root)

    if not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="Excel file not found")

    return FileResponse(
        path=str(resolved_path),
        filename=resolved_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
