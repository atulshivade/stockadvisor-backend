# watchlist.py
# StockAdvisor Backend - Watchlist Management API Routes
# Created by Digital COE Gen AI Team

from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.models.schemas import (
    User, Watchlist, WatchlistResponse, StockQuote, StockExchange
)
from app.api.auth import get_current_user
from app.services.stock_data import StockDataService

router = APIRouter()


@router.get("/", response_model=WatchlistResponse)
async def get_watchlist(current_user: User = Depends(get_current_user)):
    """
    Get user's watchlist with current stock prices.
    """
    watchlist = await Watchlist.find_one(Watchlist.user_id == str(current_user.id))
    
    if not watchlist:
        watchlist = Watchlist(user_id=str(current_user.id))
        await watchlist.insert()
    
    # Get current prices for watchlist stocks
    stocks = []
    for symbol in watchlist.symbols:
        # Try to get quote from preferred exchanges
        quote = None
        for exchange in current_user.preferred_exchanges:
            quote = await StockDataService.get_quote(symbol, exchange)
            if quote:
                stocks.append(quote)
                break
        
        # Fallback to NYSE if not found
        if not quote:
            quote = await StockDataService.get_quote(symbol, StockExchange.NYSE)
            if quote:
                stocks.append(quote)
    
    return WatchlistResponse(
        id=str(watchlist.id),
        name=watchlist.name,
        stocks=stocks,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at
    )


@router.post("/add")
async def add_to_watchlist(
    symbol: str,
    current_user: User = Depends(get_current_user)
):
    """
    Add a stock to the watchlist.
    
    - **symbol**: Stock symbol to add
    """
    symbol = symbol.upper()
    
    # Verify stock exists
    quote = None
    for exchange in current_user.preferred_exchanges:
        quote = await StockDataService.get_quote(symbol, exchange)
        if quote:
            break
    
    if not quote:
        quote = await StockDataService.get_quote(symbol, StockExchange.NYSE)
    
    if not quote:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    
    # Get user's watchlist
    watchlist = await Watchlist.find_one(Watchlist.user_id == str(current_user.id))
    
    if not watchlist:
        watchlist = Watchlist(user_id=str(current_user.id))
    
    if symbol in watchlist.symbols:
        raise HTTPException(status_code=400, detail=f"{symbol} is already in your watchlist")
    
    watchlist.symbols.append(symbol)
    watchlist.updated_at = datetime.utcnow()
    await watchlist.save()
    
    logger.info(f"User {current_user.id} added {symbol} to watchlist")
    
    return {"message": f"{symbol} added to watchlist"}


@router.delete("/{symbol}")
async def remove_from_watchlist(
    symbol: str,
    current_user: User = Depends(get_current_user)
):
    """
    Remove a stock from the watchlist.
    
    - **symbol**: Stock symbol to remove
    """
    symbol = symbol.upper()
    
    watchlist = await Watchlist.find_one(Watchlist.user_id == str(current_user.id))
    
    if not watchlist or symbol not in watchlist.symbols:
        raise HTTPException(status_code=404, detail=f"{symbol} not in watchlist")
    
    watchlist.symbols.remove(symbol)
    watchlist.updated_at = datetime.utcnow()
    await watchlist.save()
    
    logger.info(f"User {current_user.id} removed {symbol} from watchlist")
    
    return {"message": f"{symbol} removed from watchlist"}


@router.put("/rename")
async def rename_watchlist(
    name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Rename the watchlist.
    
    - **name**: New watchlist name
    """
    watchlist = await Watchlist.find_one(Watchlist.user_id == str(current_user.id))
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    watchlist.name = name
    watchlist.updated_at = datetime.utcnow()
    await watchlist.save()
    
    return {"message": f"Watchlist renamed to {name}"}

