# recommendations.py
# StockAdvisor Backend - AI Recommendations API Routes
# Created by Digital COE Gen AI Team

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from app.models.schemas import (
    User, RecommendationResponse, StockExchange
)
from app.api.auth import get_current_user
from app.ai.recommendation_engine import AIRecommendationEngine

router = APIRouter()


@router.get("/", response_model=List[RecommendationResponse])
async def get_recommendations(
    current_user: User = Depends(get_current_user),
    max_recommendations: int = Query(default=3, ge=1, le=10),
    exchanges: Optional[List[StockExchange]] = Query(default=None)
):
    """
    Get AI-powered stock recommendations personalized for the user.
    
    - **max_recommendations**: Maximum number of recommendations (1-10)
    - **exchanges**: Optional list of exchanges to consider
    
    Recommendations are based on:
    - User's risk tolerance
    - Investment goals
    - Fundamental analysis (P/E, ROE, Debt/Equity, etc.)
    - Technical indicators
    - Market sentiment
    """
    try:
        recommendations = await AIRecommendationEngine.generate_recommendations(
            user=current_user,
            exchanges=exchanges,
            max_recommendations=max_recommendations
        )
        
        logger.info(f"Generated {len(recommendations)} recommendations for user {current_user.id}")
        return recommendations
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate recommendations"
        )


@router.get("/{symbol}", response_model=RecommendationResponse)
async def get_stock_recommendation(
    symbol: str,
    exchange: StockExchange = Query(default=StockExchange.NYSE),
    current_user: User = Depends(get_current_user)
):
    """
    Get AI recommendation for a specific stock.
    
    - **symbol**: Stock symbol (e.g., AAPL, MSFT)
    - **exchange**: Stock exchange
    """
    try:
        recommendations = await AIRecommendationEngine.generate_recommendations(
            user=current_user,
            symbols=[symbol],
            exchanges=[exchange],
            max_recommendations=1
        )
        
        if not recommendations:
            raise HTTPException(
                status_code=404,
                detail=f"Unable to generate recommendation for {symbol}"
            )
        
        return recommendations[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommendation for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get stock recommendation"
        )


@router.post("/refresh", response_model=List[RecommendationResponse])
async def refresh_recommendations(
    current_user: User = Depends(get_current_user),
    max_recommendations: int = Query(default=3, ge=1, le=10)
):
    """
    Force refresh AI recommendations (bypass cache).
    
    This endpoint triggers a fresh analysis of stocks and generates
    new recommendations based on the latest market data.
    """
    try:
        from app.services.cache import CacheService
        
        # Clear cached recommendations for this user
        await CacheService.delete_pattern(f"recommendation:*:{current_user.risk_tolerance.value}")
        
        # Generate fresh recommendations
        recommendations = await AIRecommendationEngine.generate_recommendations(
            user=current_user,
            max_recommendations=max_recommendations
        )
        
        logger.info(f"Refreshed {len(recommendations)} recommendations for user {current_user.id}")
        return recommendations
        
    except Exception as e:
        logger.error(f"Error refreshing recommendations: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to refresh recommendations"
        )

