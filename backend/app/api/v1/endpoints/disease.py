"""Disease detection API endpoints (ARCH §7.2, DEV_PLAN Task 5.5).

- POST /disease/predict – Leaf image → classification + Grad-CAM + severity + advice
- GET  /disease/classes – List all 38 supported PlantVillage classes
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi import Response as FaResponse
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.rate_limit import limiter, predict_limit
from app.core.security import get_optional_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.disease import (
    DiseaseClassesResponse,
    DiseaseClassItem,
    DiseasePredictResponse,
)
from app.services.disease_service import predict_disease
from app.services.knowledge_service import get_all_classes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/disease", tags=["disease"])


@router.post(
    "/predict",
    response_model=DiseasePredictResponse,
    summary="Classify leaf disease from uploaded image",
    status_code=status.HTTP_200_OK,
    responses={
        413: {"description": "Image exceeds maximum upload size"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Disease model not loaded"},
    },
)
@limiter.limit(predict_limit)
async def disease_predict(
    request: Request,
    response: FaResponse,  # slowapi header injection requires this parameter
    file: UploadFile = File(..., description="Leaf photo (JPEG/PNG, max 10 MB)"),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> FaResponse | DiseasePredictResponse:
    """Accept a leaf photo and return disease classification with explanations."""
    settings: Settings = request.app.state.settings

    # Size guard
    contents = await file.read()
    if len(contents) > settings.max_upload_bytes:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "error": {
                    "code": "IMAGE_TOO_LARGE",
                    "message": f"Max upload size is {settings.max_upload_mb} MB",
                }
            },
        )

    user_id = current_user.id if current_user else None
    result = await predict_disease(contents, user_id=user_id, db=db, settings=settings)
    return DiseasePredictResponse(**result)


@router.get(
    "/classes",
    response_model=DiseaseClassesResponse,
    summary="List all supported disease classes",
)
async def disease_classes(db: Session = Depends(get_db)) -> DiseaseClassesResponse:
    """Return the full 38-class PlantVillage taxonomy."""
    classes_raw = get_all_classes(db)
    items = [DiseaseClassItem(**c) for c in classes_raw]
    return DiseaseClassesResponse(total_classes=len(items), classes=items)
