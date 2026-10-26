"""Crop yield prediction API endpoints (ARCH §7.2, DEV_PLAN Task 5.7).

- POST /yield/predict – Predict crop yield for a location + season
- GET  /yield/options  – List supported districts, crops, and defaults
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi import Response as FaResponse
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, predict_limit
from app.core.security import get_optional_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.yield_ import (
    YieldOptionsResponse,
    YieldPredictRequest,
    YieldPredictResponse,
)
from app.services.yield_service import get_yield_options, predict_yield

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/yield", tags=["yield"])


@router.post(
    "/predict",
    response_model=YieldPredictResponse,
    summary="Predict crop yield for a location and season",
    status_code=status.HTTP_200_OK,
    responses={
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Yield model not loaded"},
    },
)
@limiter.limit(predict_limit)
async def yield_predict(
    body: YieldPredictRequest,
    request: Request,
    response: FaResponse,  # slowapi header injection requires this parameter
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> YieldPredictResponse:
    """Accept crop, location and season parameters; return yield prediction with risk."""
    settings = request.app.state.settings
    request_data = body.model_dump()
    user_id = current_user.id if current_user else None
    result = await predict_yield(request_data, db=db, user_id=user_id, settings=settings)
    return YieldPredictResponse(**result)


@router.get(
    "/options",
    response_model=YieldOptionsResponse,
    summary="List supported districts, crops, and defaults",
)
async def yield_options() -> YieldOptionsResponse:
    """Return the full list of supported Punjab districts and crop types."""
    data = get_yield_options()
    return YieldOptionsResponse(**data)
