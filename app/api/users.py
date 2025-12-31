# users.py
# StockAdvisor Backend - User Management API Routes
# Created by Digital COE Gen AI Team

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.models.schemas import User, UserResponse, UserUpdate
from app.api.auth import get_current_user, get_password_hash

router = APIRouter()


@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user's profile."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        risk_tolerance=current_user.risk_tolerance,
        investment_goal=current_user.investment_goal,
        preferred_exchanges=current_user.preferred_exchanges,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at
    )


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update current user's profile."""
    
    if update_data.first_name is not None:
        current_user.first_name = update_data.first_name
    
    if update_data.last_name is not None:
        current_user.last_name = update_data.last_name
    
    if update_data.risk_tolerance is not None:
        current_user.risk_tolerance = update_data.risk_tolerance
    
    if update_data.investment_goal is not None:
        current_user.investment_goal = update_data.investment_goal
    
    if update_data.preferred_exchanges is not None:
        current_user.preferred_exchanges = update_data.preferred_exchanges
    
    current_user.updated_at = datetime.utcnow()
    await current_user.save()
    
    logger.info(f"User {current_user.id} updated profile")
    
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        risk_tolerance=current_user.risk_tolerance,
        investment_goal=current_user.investment_goal,
        preferred_exchanges=current_user.preferred_exchanges,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at
    )


@router.put("/password")
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user)
):
    """Change user's password."""
    from app.api.auth import verify_password
    from app.config import settings
    
    # Verify current password
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Validate new password
    if len(new_password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(new_password)
    current_user.updated_at = datetime.utcnow()
    await current_user.save()
    
    logger.info(f"User {current_user.id} changed password")
    
    return {"message": "Password updated successfully"}


@router.delete("/account")
async def delete_account(
    password: str,
    current_user: User = Depends(get_current_user)
):
    """Delete user's account."""
    from app.api.auth import verify_password
    from app.models.schemas import Portfolio, Watchlist, Transaction
    
    # Verify password
    if not verify_password(password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    
    # Delete user's data
    await Portfolio.find(Portfolio.user_id == str(current_user.id)).delete()
    await Watchlist.find(Watchlist.user_id == str(current_user.id)).delete()
    await Transaction.find(Transaction.user_id == str(current_user.id)).delete()
    
    # Delete user
    await current_user.delete()
    
    logger.info(f"User {current_user.id} deleted account")
    
    return {"message": "Account deleted successfully"}

