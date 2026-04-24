import os
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/quotes", tags=["quotes"])
logger = logging.getLogger(__name__)

QUOTES_DIR = "backend/generated_quotes"


@router.get("/{filename}")
async def download_quote(filename: str):
    filepath = os.path.join(QUOTES_DIR, filename)

    if not os.path.exists(filepath):
        logger.warning(f"[QuoteDownload] File not found: {filename}")
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@router.delete("/{session_id}")
async def cleanup_quote(session_id: str):
    deleted = []
    if os.path.exists(QUOTES_DIR):
        for f in os.listdir(QUOTES_DIR):
            if session_id in f:
                filepath = os.path.join(QUOTES_DIR, f)
                os.remove(filepath)
                deleted.append(f)
                logger.info(f"[QuoteCleanup] Deleted: {f}")

    return {"deleted": deleted}