"""
Capsule CRUD and public feed endpoints.

Requirements: 3.1, 3.2, 3.3-3.6, 4.1, 4.2, 8.1, 8.5, 8.6, 9.4-9.7, 14.6
Timezone Requirements: 1.4, 2.1, 2.2, 2.3, 2.5, 4.1, 4.2, 5.2
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import io

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.capsule import (
    CapsuleCreateRequest,
    CapsuleResponse,
    CapsuleListResponse,
    PublicCapsuleResponse,
    PublicFeedResponse,
    MediaUploadResponse,
)
from app.services.capsule_service import (
    CapsuleService,
    InvalidUnlockDateError,
    ValidationError,
    CapsuleNotFoundError,
)
from app.services.locking_mechanism import AccessDeniedError
from app.services.media_service import MediaService, InvalidFileError
from app.services.storage_adapter import UploadFailedError, StorageAdapter
from app.services.timezone_service import InvalidTimezoneError
from app.config import settings
from app.cache import (
    cache_get,
    cache_set,
    invalidate_capsule_caches,
)

router = APIRouter(prefix="/api/capsules", tags=["capsules"])
public_router = APIRouter(prefix="/api/public", tags=["public"])


# ---------------------------------------------------------------------------
# Helper: detect media type from content_type
# ---------------------------------------------------------------------------

def _detect_media_type(content_type: Optional[str]) -> str:
    if not content_type:
        raise InvalidFileError("Missing content type")
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("audio/"):
        return "audio"
    if content_type.startswith("image/"):
        return "image"
    raise InvalidFileError(f"Unsupported content type: {content_type}")


# ---------------------------------------------------------------------------
# Capsule CRUD endpoints (authenticated)
# ---------------------------------------------------------------------------


@router.post("", response_model=CapsuleResponse, status_code=status.HTTP_201_CREATED)
def create_capsule(
    body: CapsuleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new time capsule with timezone support (Req 1.4, 2.1-2.5, 3.1, 3.2, 4.1, 4.2, 5.2)."""
    svc = CapsuleService(db)
    try:
        capsule, dst_adjustment_message = svc.create_capsule(
            user_id=current_user.id,
            title=body.title,
            text_content=body.text_content,
            unlock_date=body.unlock_date,
            tz_str=body.timezone,
            is_public=body.is_public,
        )
    except InvalidTimezoneError as exc:
        # Req 2.2: Return descriptive error for invalid timezone
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except InvalidUnlockDateError as exc:
        # Req 2.5: Reject if unlock date is not in future after UTC conversion
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # Invalidate caches after capsule creation
    invalidate_capsule_caches(current_user.id)

    # Format unlock_date_local for response (Req 4.1)
    unlock_date_local = svc._format_unlock_date_local(capsule.unlock_date, capsule.timezone)

    return CapsuleResponse(
        id=capsule.id,
        title=capsule.title,
        text_content=None,  # newly created → locked
        media_urls=[],
        transcriptions=[],
        unlock_date=capsule.unlock_date,
        timezone=capsule.timezone,
        unlock_date_local=unlock_date_local,
        status=capsule.status,
        is_public=capsule.is_public,
        created_at=capsule.created_at,
        time_until_unlock=None,
        user_id=capsule.user_id,
        dst_adjustment_message=dst_adjustment_message,  # Req 5.2: Inform user of DST adjustment
    )


@router.get("/{capsule_id}", response_model=CapsuleResponse)
def get_capsule(
    capsule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a capsule by ID (Req 8.1)."""
    svc = CapsuleService(db)
    try:
        data = svc.get_capsule(capsule_id, current_user.id)
    except CapsuleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capsule not found")
    except AccessDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error loading capsule {capsule_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load capsule")

    return CapsuleResponse(**data)


@router.post("/{capsule_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
def trigger_ai_analysis(
    capsule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger AI analysis for an unlocked capsule."""
    from app.models.capsule import Capsule
    from app.models.ai_analysis import AIAnalysis

    capsule = db.query(Capsule).filter(Capsule.id == capsule_id).first()
    if not capsule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capsule not found")
    if capsule.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if capsule.status != "unlocked":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Capsule must be unlocked")

    # Check if analysis already exists and is completed
    existing = db.query(AIAnalysis).filter(AIAnalysis.capsule_id == capsule_id).first()
    if existing and existing.processing_status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="AI analysis already completed")

    # Trigger async analysis via Celery
    try:
        from app.tasks.ai_analysis import analyze_capsule_task
        analyze_capsule_task.apply_async(args=[capsule_id])
    except Exception:
        # If Celery isn't available, run synchronously
        from app.services.ai_service import AIService
        ai_service = AIService()
        ai_service.analyze_capsule(capsule_id, db)

    return {"message": "AI analysis triggered", "capsule_id": capsule_id}


@router.get("", response_model=CapsuleListResponse)
def list_capsules(
    filter_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List current user's capsules with optional filters (Req 8.1, 8.5, 8.6, 14.5, 14.6)."""
    # Only cache unfiltered/unsearched dashboard requests at default pagination
    cache_key = f"user_capsules:{current_user.id}"
    if not filter_status and not search and limit == 50 and offset == 0:
        cached = cache_get(cache_key)
        if cached is not None:
            return CapsuleListResponse(
                capsules=[CapsuleResponse(**c) for c in cached["capsules"]],
                total=cached["total"],
            )

    svc = CapsuleService(db)
    capsules = svc.list_user_capsules(
        user_id=current_user.id,
        filter_status=filter_status,
        search_query=search,
        limit=limit,
        offset=offset,
    )
    result = CapsuleListResponse(
        capsules=[CapsuleResponse(**c) for c in capsules],
        total=len(capsules),
    )

    # Cache only unfiltered default-page results (TTL 30s)
    if not filter_status and not search and limit == 50 and offset == 0:
        cache_set(cache_key, {"capsules": capsules, "total": len(capsules)}, ttl=30)

    return result


@router.post("/{capsule_id}/media", response_model=MediaUploadResponse)
async def upload_media(
    capsule_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload media to a capsule (Req 3.3, 3.4, 3.5, 3.6)."""
    from app.models.capsule import Capsule

    # Verify capsule exists and belongs to user
    capsule = db.query(Capsule).filter(Capsule.id == capsule_id).first()
    if not capsule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capsule not found")
    if capsule.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if capsule.status != "locked":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add media to an unlocked capsule",
        )

    # Detect media type and upload
    media_svc = MediaService()
    try:
        media_type = _detect_media_type(file.content_type)
        url = await media_svc.upload_media(file, current_user.id, media_type)
    except InvalidFileError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except UploadFailedError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Append URL to capsule's media_urls
    current_urls = list(capsule.media_urls or [])
    current_urls.append(url)
    capsule.media_urls = current_urls
    db.commit()
    db.refresh(capsule)

    # Invalidate caches after media upload
    invalidate_capsule_caches(current_user.id)

    return MediaUploadResponse(url=url, message="Media uploaded successfully")


# ---------------------------------------------------------------------------
# Media proxy — streams S3 objects through the backend so the browser
# doesn't need direct S3 access (avoids presigned-URL / CORS issues).
# ---------------------------------------------------------------------------

@router.get("/{capsule_id}/media/{file_key}")
def proxy_media(
    capsule_id: int,
    file_key: str,
    db: Session = Depends(get_db),
):
    """Proxy media file from S3 through the backend.
    
    Access control is based on capsule status:
    - Unlocked capsules: media is accessible (content is revealed)
    - Locked capsules: media is blocked
    """
    from app.models.capsule import Capsule

    capsule = db.query(Capsule).filter(Capsule.id == capsule_id).first()
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    # Only serve media for unlocked capsules
    if capsule.status == "locked":
        raise HTTPException(status_code=403, detail="Capsule is locked")

    storage = StorageAdapter()
    if not storage.use_s3:
        raise HTTPException(status_code=404, detail="S3 not configured")

    try:
        resp = storage.s3_client.get_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=file_key,
        )
        content_type = resp.get("ContentType", "application/octet-stream")
        body = resp["Body"]
        return StreamingResponse(body, media_type=content_type)
    except Exception:
        raise HTTPException(status_code=404, detail="Media not found")


# ---------------------------------------------------------------------------
# Public feed endpoint (unauthenticated access allowed) — Req 9.4-9.7
# ---------------------------------------------------------------------------


@public_router.get("/capsules", response_model=PublicFeedResponse)
def get_public_feed(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get recently unlocked public capsules. No auth required. (Req 9.4-9.7, 14.6)"""
    # Cache only the default first page
    cache_key = "public_feed"
    if limit == 50 and offset == 0:
        cached = cache_get(cache_key)
        if cached is not None:
            return PublicFeedResponse(
                capsules=[PublicCapsuleResponse(**c) for c in cached["capsules"]],
                total=cached["total"],
            )

    svc = CapsuleService(db)
    capsules = svc.get_public_feed(limit=limit, offset=offset)
    result = PublicFeedResponse(
        capsules=[PublicCapsuleResponse(**c) for c in capsules],
        total=len(capsules),
    )

    # Cache only the default first page (TTL 60s)
    if limit == 50 and offset == 0:
        cache_set(cache_key, {"capsules": capsules, "total": len(capsules)}, ttl=60)

    return result
