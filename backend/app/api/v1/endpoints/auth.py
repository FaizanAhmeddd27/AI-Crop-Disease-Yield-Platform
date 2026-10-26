"""Authentication and user management endpoints (ARCH §8.2, §13, DEV_PLAN 5.14)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.db.models import PredictionDisease, PredictionYield, User
from app.db.session import get_db
from app.schemas.auth import (
    DiseaseHistoryItem,
    HistoryStatsResponse,
    PasswordChange,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
    YieldHistoryItem,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    payload: UserRegister,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Register a new farmer or agronomist account and return an access token."""
    email = payload.email.lower().strip()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    user = User(
        email=email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        role=payload.role,
        preferred_language=payload.preferred_language,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role})
    expires_in = settings.access_token_expire_minutes * 60

    logger.info("New user registered", extra={"user_id": user.id, "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",  # noqa: S106 - OAuth2 scheme keyword, not a secret
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT token",
)
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Login with email and password to receive an access token."""
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Please contact support.",
        )

    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role})
    expires_in = settings.access_token_expire_minutes * 60

    logger.info("User logged in successfully", extra={"user_id": user.id})
    return TokenResponse(
        access_token=token,
        token_type="bearer",  # noqa: S106 - OAuth2 scheme keyword, not a secret
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the profile of the authenticated user."""
    return UserResponse.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Update profile information (full_name, phone_number, preferred_language)."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.phone_number is not None:
        current_user.phone_number = payload.phone_number
    if payload.preferred_language is not None:
        current_user.preferred_language = payload.preferred_language

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.post(
    "/change-password",
    summary="Change account password",
)
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Change the authenticated user's password."""
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    current_user.hashed_password = get_password_hash(payload.new_password)
    db.add(current_user)
    db.commit()
    logger.info("Password updated", extra={"user_id": current_user.id})
    return {"status": "ok", "message": "Password updated successfully."}


@router.get(
    "/history/disease",
    response_model=list[DiseaseHistoryItem],
    summary="Get user's disease scan history",
)
def get_disease_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DiseaseHistoryItem]:
    """Retrieve chronologically ordered list of disease predictions for the authenticated user."""
    records = (
        db.query(PredictionDisease)
        .filter(PredictionDisease.user_id == current_user.id)
        .order_by(PredictionDisease.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [DiseaseHistoryItem.model_validate(r) for r in records]


@router.delete(
    "/history/disease/{prediction_id}",
    summary="Delete a disease scan record from history",
)
def delete_disease_history_item(
    prediction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete a user-owned disease prediction (NFR-PR-003 privacy data deletion)."""
    record = (
        db.query(PredictionDisease)
        .filter(
            PredictionDisease.id == prediction_id,
            PredictionDisease.user_id == current_user.id,
        )
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disease prediction not found or not owned by user.",
        )

    db.delete(record)
    db.commit()
    return {"status": "ok", "message": "Record deleted successfully."}


@router.get(
    "/history/yield",
    response_model=list[YieldHistoryItem],
    summary="Get user's crop yield history",
)
def get_yield_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[YieldHistoryItem]:
    """Retrieve chronologically ordered list of yield predictions for the authenticated user."""
    records = (
        db.query(PredictionYield)
        .filter(PredictionYield.user_id == current_user.id)
        .order_by(PredictionYield.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [YieldHistoryItem.model_validate(r) for r in records]


@router.delete(
    "/history/yield/{prediction_id}",
    summary="Delete a yield prediction record from history",
)
def delete_yield_history_item(
    prediction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete a user-owned yield prediction (NFR-PR-003 privacy data deletion)."""
    record = (
        db.query(PredictionYield)
        .filter(
            PredictionYield.id == prediction_id,
            PredictionYield.user_id == current_user.id,
        )
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Yield prediction not found or not owned by user.",
        )

    db.delete(record)
    db.commit()
    return {"status": "ok", "message": "Record deleted successfully."}


@router.get(
    "/history/stats",
    response_model=HistoryStatsResponse,
    summary="Get aggregated summary statistics for the user",
)
def get_history_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryStatsResponse:
    """Get aggregated metrics for the user dashboard."""
    disease_query = db.query(PredictionDisease).filter(PredictionDisease.user_id == current_user.id)
    total_disease = disease_query.count()
    healthy_count = disease_query.filter(PredictionDisease.is_healthy.is_(True)).count()
    diseased_count = disease_query.filter(PredictionDisease.is_healthy.is_(False)).count()

    yield_query = db.query(PredictionYield).filter(PredictionYield.user_id == current_user.id)
    total_yield = yield_query.count()
    avg_yield = (
        db.query(func.avg(PredictionYield.predicted_yield_tha))
        .filter(PredictionYield.user_id == current_user.id)
        .scalar()
    )

    return HistoryStatsResponse(
        total_disease_scans=total_disease,
        healthy_count=healthy_count,
        diseased_count=diseased_count,
        total_yield_forecasts=total_yield,
        avg_predicted_yield_tha=float(avg_yield) if avg_yield is not None else None,
    )
