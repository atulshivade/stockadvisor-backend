# stock_data.py
# StockAdvisor Backend - Real-time Stock Data Service
# Created by Digital COE Gen AI Team

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import httpx
from loguru import logger
import yfinance as yf

from app.config import settings, EXCHANGE_CONFIG
from app.models.schemas import StockQuote, StockExchange, StockSearch
from app.services.cache import CacheService


class StockDataService:
    """Service for fetching real-time stock data from multiple providers."""
    
    _instance = None
    _is_running = False
    _price_subscribers: Dict[str, List] = {}
    
    @classmethod
    def initialize(cls):
        """Initialize the stock data service."""
        cls._instance = cls()
        cls._is_running = True
        logger.info("Stock data service initialized")
    
    @classmethod
    def shutdown(cls):
        """Shutdown the stock data service."""
        cls._is_running = False
        logger.info("Stock data service shutdown")
    
    @classmethod
    async def start_price_updater(cls):
        """Background task to update stock prices periodically."""
        while cls._is_running:
            try:
                # Get all subscribed symbols
                symbols = list(cls._price_subscribers.keys())
                if symbols:
                    await cls.batch_update_prices(symbols)
                
                await asyncio.sleep(settings.PRICE_UPDATE_INTERVAL)
            except Exception as e:
                logger.error(f"Price updater error: {e}")
                await asyncio.sleep(5)
    
    @classmethod
    async def get_quote(cls, symbol: str, exchange: StockExchange) -> Optional[StockQuote]:
        """
        Get real-time quote for a stock.
        
        Args:
            symbol: Stock symbol
            exchange: Stock exchange
            
        Returns:
            StockQuote object or None if not found
        """
        # Check cache first
        cache_key = f"quote:{symbol}:{exchange.value}"
        cached = await CacheService.get(cache_key)
        if cached:
            return StockQuote(**cached)
        
        try:
            # Get exchange-specific symbol suffix
            suffix = EXCHANGE_CONFIG.get(exchange.value, {}).get("api_suffix", "")
            full_symbol = f"{symbol}{suffix}"
            
            # Try yfinance first (free, supports most international markets)
            quote = await cls._fetch_from_yfinance(full_symbol, symbol, exchange)
            
            if not quote:
                # Fallback to Alpha Vantage
                quote = await cls._fetch_from_alpha_vantage(symbol, exchange)
            
            if not quote:
                # Fallback to IEX Cloud (US stocks)
                if exchange in [StockExchange.NYSE, StockExchange.NASDAQ]:
                    quote = await cls._fetch_from_iex(symbol, exchange)
            
            if quote:
                # Cache the result
                await CacheService.set(cache_key, quote.model_dump(), ttl=30)
                return quote
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None
    
    @classmethod
    async def _fetch_from_yfinance(
        cls, 
        full_symbol: str, 
        symbol: str, 
        exchange: StockExchange
    ) -> Optional[StockQuote]:
        """Fetch stock data from Yahoo Finance."""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(None, yf.Ticker, full_symbol)
            
            # Get current info
            info = await loop.run_in_executor(None, lambda: ticker.info)
            
            if not info or 'regularMarketPrice' not in info:
                return None
            
            current_price = info.get('regularMarketPrice', 0)
            previous_close = info.get('previousClose', current_price)
            
            return StockQuote(
                symbol=symbol,
                name=info.get('longName', info.get('shortName', symbol)),
                exchange=exchange,
                current_price=current_price,
                previous_close=previous_close,
                change=current_price - previous_close,
                change_percent=((current_price - previous_close) / previous_close * 100) if previous_close > 0 else 0,
                day_high=info.get('dayHigh', current_price),
                day_low=info.get('dayLow', current_price),
                volume=info.get('volume', 0),
                market_cap=info.get('marketCap'),
                pe_ratio=info.get('trailingPE'),
                dividend_yield=info.get('dividendYield'),
                week_52_high=info.get('fiftyTwoWeekHigh', current_price),
                week_52_low=info.get('fiftyTwoWeekLow', current_price),
                last_updated=datetime.utcnow()
            )
        except Exception as e:
            logger.warning(f"yfinance fetch failed for {full_symbol}: {e}")
            return None
    
    @classmethod
    async def _fetch_from_alpha_vantage(
        cls, 
        symbol: str, 
        exchange: StockExchange
    ) -> Optional[StockQuote]:
        """Fetch stock data from Alpha Vantage."""
        if not settings.ALPHA_VANTAGE_API_KEY:
            return None
            
        try:
            url = (
                f"https://www.alphavantage.co/query"
                f"?function=GLOBAL_QUOTE"
                f"&symbol={symbol}"
                f"&apikey={settings.ALPHA_VANTAGE_API_KEY}"
            )
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                data = response.json()
            
            quote_data = data.get('Global Quote', {})
            if not quote_data:
                return None
            
            current_price = float(quote_data.get('05. price', 0))
            previous_close = float(quote_data.get('08. previous close', current_price))
            
            return StockQuote(
                symbol=symbol,
                name=symbol,  # Alpha Vantage doesn't return company name in quote
                exchange=exchange,
                current_price=current_price,
                previous_close=previous_close,
                change=float(quote_data.get('09. change', 0)),
                change_percent=float(quote_data.get('10. change percent', '0').rstrip('%')),
                day_high=float(quote_data.get('03. high', current_price)),
                day_low=float(quote_data.get('04. low', current_price)),
                volume=int(quote_data.get('06. volume', 0)),
                market_cap=None,
                pe_ratio=None,
                dividend_yield=None,
                week_52_high=current_price,
                week_52_low=current_price,
                last_updated=datetime.utcnow()
            )
        except Exception as e:
            logger.warning(f"Alpha Vantage fetch failed for {symbol}: {e}")
            return None
    
    @classmethod
    async def _fetch_from_iex(
        cls, 
        symbol: str, 
        exchange: StockExchange
    ) -> Optional[StockQuote]:
        """Fetch stock data from IEX Cloud (US stocks only)."""
        if not settings.IEX_CLOUD_API_KEY:
            return None
            
        try:
            url = (
                f"https://cloud.iexapis.com/stable/stock/{symbol}/quote"
                f"?token={settings.IEX_CLOUD_API_KEY}"
            )
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                data = response.json()
            
            if not data:
                return None
            
            return StockQuote(
                symbol=symbol,
                name=data.get('companyName', symbol),
                exchange=exchange,
                current_price=data.get('latestPrice', 0),
                previous_close=data.get('previousClose', 0),
                change=data.get('change', 0),
                change_percent=data.get('changePercent', 0) * 100,
                day_high=data.get('high', 0),
                day_low=data.get('low', 0),
                volume=data.get('volume', 0),
                market_cap=data.get('marketCap'),
                pe_ratio=data.get('peRatio'),
                dividend_yield=None,
                week_52_high=data.get('week52High', 0),
                week_52_low=data.get('week52Low', 0),
                last_updated=datetime.utcnow()
            )
        except Exception as e:
            logger.warning(f"IEX Cloud fetch failed for {symbol}: {e}")
            return None
    
    @classmethod
    async def search_stocks(
        cls, 
        query: str, 
        exchange: Optional[StockExchange] = None,
        limit: int = 10
    ) -> List[StockSearch]:
        """
        Search for stocks by symbol or company name.
        
        Args:
            query: Search query
            exchange: Optional exchange filter
            limit: Maximum results to return
            
        Returns:
            List of matching stocks
        """
        results = []
        
        try:
            # Use yfinance for search
            loop = asyncio.get_event_loop()
            tickers = await loop.run_in_executor(
                None, 
                lambda: yf.Tickers(query).tickers
            )
            
            for symbol, ticker in list(tickers.items())[:limit]:
                try:
                    info = await loop.run_in_executor(None, lambda: ticker.info)
                    if info:
                        results.append(StockSearch(
                            symbol=symbol,
                            name=info.get('longName', info.get('shortName', symbol)),
                            exchange=StockExchange.NYSE,  # Default, should be detected
                            type="stock"
                        ))
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Stock search error: {e}")
        
        return results
    
    @classmethod
    async def get_price_history(
        cls, 
        symbol: str, 
        exchange: StockExchange,
        period: str = "1mo"
    ) -> List[Dict]:
        """
        Get historical price data for a stock.
        
        Args:
            symbol: Stock symbol
            exchange: Stock exchange
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
            
        Returns:
            List of historical price data
        """
        try:
            suffix = EXCHANGE_CONFIG.get(exchange.value, {}).get("api_suffix", "")
            full_symbol = f"{symbol}{suffix}"
            
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(None, yf.Ticker, full_symbol)
            
            history = await loop.run_in_executor(
                None, 
                lambda: ticker.history(period=period)
            )
            
            return [
                {
                    "date": str(date),
                    "open": row["Open"],
                    "high": row["High"],
                    "low": row["Low"],
                    "close": row["Close"],
                    "volume": row["Volume"]
                }
                for date, row in history.iterrows()
            ]
        except Exception as e:
            logger.error(f"Price history error for {symbol}: {e}")
            return []
    
    @classmethod
    async def batch_update_prices(cls, symbols: List[str]):
        """Update prices for multiple symbols at once."""
        try:
            loop = asyncio.get_event_loop()
            tickers = await loop.run_in_executor(
                None, 
                lambda: yf.Tickers(" ".join(symbols))
            )
            
            for symbol in symbols:
                try:
                    ticker = tickers.tickers.get(symbol)
                    if ticker:
                        info = await loop.run_in_executor(None, lambda: ticker.info)
                        if info and 'regularMarketPrice' in info:
                            # Notify subscribers
                            await cls._notify_price_update(symbol, info)
                except:
                    pass
        except Exception as e:
            logger.error(f"Batch price update error: {e}")
    
    @classmethod
    async def _notify_price_update(cls, symbol: str, info: dict):
        """Notify subscribers of price updates."""
        from app.services.websocket_manager import WebSocketManager
        
        update = {
            "symbol": symbol,
            "price": info.get('regularMarketPrice', 0),
            "change": info.get('regularMarketChange', 0),
            "change_percent": info.get('regularMarketChangePercent', 0),
            "volume": info.get('regularMarketVolume', 0),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await WebSocketManager.broadcast_price_update(update)
    
    @classmethod
    def subscribe_to_prices(cls, symbol: str, callback):
        """Subscribe to price updates for a symbol."""
        if symbol not in cls._price_subscribers:
            cls._price_subscribers[symbol] = []
        cls._price_subscribers[symbol].append(callback)
    
    @classmethod
    def unsubscribe_from_prices(cls, symbol: str, callback):
        """Unsubscribe from price updates for a symbol."""
        if symbol in cls._price_subscribers:
            cls._price_subscribers[symbol].remove(callback)
            if not cls._price_subscribers[symbol]:
                del cls._price_subscribers[symbol]

