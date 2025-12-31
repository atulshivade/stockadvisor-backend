# stocks.py
# StockAdvisor Backend - Stock Data API Routes
# Created by Digital COE Gen AI Team

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from app.models.schemas import (
    User, StockQuote, StockSearch, StockExchange
)
from app.api.auth import get_current_user
from app.services.stock_data import StockDataService

router = APIRouter()


@router.get("/quote/{symbol}", response_model=StockQuote)
async def get_stock_quote(
    symbol: str,
    exchange: StockExchange = Query(default=StockExchange.NYSE),
    current_user: User = Depends(get_current_user)
):
    """
    Get real-time stock quote.
    
    - **symbol**: Stock symbol (e.g., AAPL, MSFT, GOOGL)
    - **exchange**: Stock exchange (NYSE, NASDAQ, LSE, etc.)
    
    Returns current price, change, volume, and other quote data.
    """
    quote = await StockDataService.get_quote(symbol.upper(), exchange)
    
    if not quote:
        raise HTTPException(
            status_code=404,
            detail=f"Stock {symbol} not found on {exchange.value}"
        )
    
    return quote


@router.get("/search", response_model=List[StockSearch])
async def search_stocks(
    q: str = Query(..., min_length=1, description="Search query"),
    exchange: Optional[StockExchange] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user)
):
    """
    Search for stocks by symbol or company name.
    
    - **q**: Search query (symbol or company name)
    - **exchange**: Optional exchange filter
    - **limit**: Maximum results (1-50)
    """
    results = await StockDataService.search_stocks(
        query=q.upper(),
        exchange=exchange,
        limit=limit
    )
    
    return results


@router.get("/history/{symbol}")
async def get_price_history(
    symbol: str,
    exchange: StockExchange = Query(default=StockExchange.NYSE),
    period: str = Query(default="1mo", regex="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|max)$"),
    current_user: User = Depends(get_current_user)
):
    """
    Get historical price data for a stock.
    
    - **symbol**: Stock symbol
    - **exchange**: Stock exchange
    - **period**: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
    """
    history = await StockDataService.get_price_history(
        symbol.upper(),
        exchange,
        period
    )
    
    if not history:
        raise HTTPException(
            status_code=404,
            detail=f"Price history not found for {symbol}"
        )
    
    return {"symbol": symbol, "exchange": exchange, "period": period, "data": history}


@router.get("/batch", response_model=List[StockQuote])
async def get_batch_quotes(
    symbols: str = Query(..., description="Comma-separated stock symbols"),
    exchange: StockExchange = Query(default=StockExchange.NYSE),
    current_user: User = Depends(get_current_user)
):
    """
    Get quotes for multiple stocks at once.
    
    - **symbols**: Comma-separated list of stock symbols (max 20)
    - **exchange**: Stock exchange
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")][:20]
    
    quotes = []
    for symbol in symbol_list:
        quote = await StockDataService.get_quote(symbol, exchange)
        if quote:
            quotes.append(quote)
    
    return quotes


@router.get("/market-status/{exchange}")
async def get_market_status(
    exchange: StockExchange,
    current_user: User = Depends(get_current_user)
):
    """
    Get market open/close status for an exchange.
    
    - **exchange**: Stock exchange to check
    """
    is_open = StockDataService.is_market_open(exchange)
    
    from app.config import EXCHANGE_CONFIG
    config = EXCHANGE_CONFIG.get(exchange.value, {})
    
    return {
        "exchange": exchange.value,
        "name": config.get("name", exchange.value),
        "country": config.get("country"),
        "currency": config.get("currency"),
        "timezone": config.get("timezone"),
        "is_open": is_open,
        "open_time": config.get("open_time"),
        "close_time": config.get("close_time")
    }


@router.get("/exchanges", response_model=List[dict])
async def get_supported_exchanges(
    current_user: User = Depends(get_current_user)
):
    """Get list of all supported stock exchanges."""
    from app.config import EXCHANGE_CONFIG
    
    exchanges = []
    for exchange_code, config in EXCHANGE_CONFIG.items():
        exchanges.append({
            "code": exchange_code,
            "name": config["name"],
            "country": config["country"],
            "currency": config["currency"],
            "timezone": config["timezone"],
            "is_open": StockDataService.is_market_open(StockExchange(exchange_code))
        })
    
    return exchanges

