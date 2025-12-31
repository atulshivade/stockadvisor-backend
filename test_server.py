# test_server.py
# StockAdvisor Backend - Lightweight Test Server (No Database Required)
# Created by Atul Shivade (atul.shivade@gmail.com)
# Uses MOCK DATA to work without external API dependencies

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import json
import random

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from jose import jwt
from loguru import logger
import uvicorn

# ============== Configuration ==============
SECRET_KEY = "test-secret-key-for-development"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ============== MOCK STOCK DATA ==============
# Real-like mock data for testing (since yfinance has SSL issues)
MOCK_STOCKS = {
    "AAPL": {"name": "Apple Inc.", "price": 257.45, "prev_close": 255.80, "high": 259.00, "low": 254.50, "volume": 45234567, "market_cap": 3950000000000, "pe_ratio": 34.2, "week_52_high": 260.10, "week_52_low": 164.08},
    "MSFT": {"name": "Microsoft Corporation", "price": 439.12, "prev_close": 436.90, "high": 441.50, "low": 435.20, "volume": 18234567, "market_cap": 3260000000000, "pe_ratio": 37.5, "week_52_high": 448.31, "week_52_low": 366.50},
    "GOOGL": {"name": "Alphabet Inc.", "price": 193.78, "prev_close": 192.45, "high": 195.20, "low": 191.30, "volume": 22345678, "market_cap": 2400000000000, "pe_ratio": 24.8, "week_52_high": 201.20, "week_52_low": 140.53},
    "AMZN": {"name": "Amazon.com Inc.", "price": 224.91, "prev_close": 223.10, "high": 226.50, "low": 222.00, "volume": 35678901, "market_cap": 2350000000000, "pe_ratio": 46.2, "week_52_high": 234.00, "week_52_low": 171.00},
    "NVDA": {"name": "NVIDIA Corporation", "price": 137.93, "prev_close": 135.80, "high": 140.20, "low": 134.50, "volume": 98765432, "market_cap": 3380000000000, "pe_ratio": 54.3, "week_52_high": 152.89, "week_52_low": 60.70},
    "TSLA": {"name": "Tesla Inc.", "price": 454.13, "prev_close": 448.50, "high": 460.00, "low": 445.00, "volume": 67890123, "market_cap": 1450000000000, "pe_ratio": 112.5, "week_52_high": 488.54, "week_52_low": 167.41},
    "META": {"name": "Meta Platforms Inc.", "price": 603.35, "prev_close": 598.20, "high": 608.50, "low": 595.00, "volume": 12345678, "market_cap": 1550000000000, "pe_ratio": 28.9, "week_52_high": 629.79, "week_52_low": 414.50},
    "AMD": {"name": "Advanced Micro Devices", "price": 124.67, "prev_close": 122.30, "high": 126.00, "low": 121.50, "volume": 45678901, "market_cap": 202000000000, "pe_ratio": 105.2, "week_52_high": 227.30, "week_52_low": 123.04},
    "INTC": {"name": "Intel Corporation", "price": 20.13, "prev_close": 20.45, "high": 20.80, "low": 19.90, "volume": 56789012, "market_cap": 86500000000, "pe_ratio": None, "week_52_high": 51.28, "week_52_low": 18.51},
    "NFLX": {"name": "Netflix Inc.", "price": 909.05, "prev_close": 901.20, "high": 915.00, "low": 898.00, "volume": 3456789, "market_cap": 389000000000, "pe_ratio": 49.8, "week_52_high": 941.75, "week_52_low": 542.01},
    "JPM": {"name": "JPMorgan Chase & Co.", "price": 246.78, "prev_close": 244.90, "high": 248.50, "low": 243.00, "volume": 8901234, "market_cap": 700000000000, "pe_ratio": 13.1, "week_52_high": 266.39, "week_52_low": 189.82},
    "V": {"name": "Visa Inc.", "price": 320.45, "prev_close": 318.20, "high": 322.00, "low": 316.50, "volume": 5678901, "market_cap": 597000000000, "pe_ratio": 31.5, "week_52_high": 324.81, "week_52_low": 266.03},
}

# ============== Data Models ==============
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    risk_tolerance: str = "moderate"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class StockQuote(BaseModel):
    symbol: str
    name: str
    current_price: float
    previous_close: float
    change: float
    change_percent: float
    day_high: float
    day_low: float
    volume: int
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    week_52_high: float
    week_52_low: float
    last_updated: str

class Recommendation(BaseModel):
    id: str
    symbol: str
    name: str
    recommendation_type: str
    confidence_score: float
    current_price: float
    target_price: float
    potential_return: float
    rationale: str

# ============== In-Memory Storage ==============
users_db: Dict[str, dict] = {}
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ============== Helper Functions ==============
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None or email not in users_db:
            raise HTTPException(status_code=401, detail="Invalid token")
        return users_db[email]
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_mock_quote(symbol: str) -> Optional[StockQuote]:
    """Get mock stock data with slight random variations for realism."""
    if symbol.upper() not in MOCK_STOCKS:
        return None
    
    data = MOCK_STOCKS[symbol.upper()]
    
    # Add slight random variation to simulate live data
    variation = random.uniform(-0.5, 0.5)
    current_price = round(data["price"] + variation, 2)
    
    change = round(current_price - data["prev_close"], 2)
    change_percent = round((change / data["prev_close"]) * 100, 2)
    
    return StockQuote(
        symbol=symbol.upper(),
        name=data["name"],
        current_price=current_price,
        previous_close=data["prev_close"],
        change=change,
        change_percent=change_percent,
        day_high=data["high"],
        day_low=data["low"],
        volume=data["volume"],
        market_cap=data["market_cap"],
        pe_ratio=data["pe_ratio"],
        week_52_high=data["week_52_high"],
        week_52_low=data["week_52_low"],
        last_updated=datetime.utcnow().isoformat()
    )

# ============== FastAPI App ==============
app = FastAPI(
    title="StockAdvisor API - Test Server",
    description="Lightweight test server for StockAdvisor with MOCK DATA (No external dependencies)",
    version="1.0.0-test"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== Routes ==============

@app.get("/")
async def root():
    """Root endpoint - Health check."""
    return {
        "name": "StockAdvisor API - Test Server",
        "version": "1.0.0-test",
        "status": "healthy",
        "creator": "Atul Shivade (atul.shivade@gmail.com)",
        "message": "Welcome! API Docs at /docs",
        "note": "Using MOCK DATA (real-time data unavailable due to SSL/proxy)"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "database": "in-memory", "data_source": "mock", "timestamp": datetime.utcnow().isoformat()}

# ============== Auth Routes ==============

@app.post("/api/v1/auth/register", response_model=TokenResponse)
async def register(user: UserCreate):
    """Register a new user."""
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    users_db[user.email] = {
        "email": user.email,
        "password": user.password,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "risk_tolerance": user.risk_tolerance
    }
    
    token = create_access_token({"sub": user.email})
    logger.info(f"User registered: {user.email}")
    return TokenResponse(access_token=token)

@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token."""
    user = users_db.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": form_data.username})
    logger.info(f"User logged in: {form_data.username}")
    return TokenResponse(access_token=token)

@app.get("/api/v1/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    return {
        "email": current_user["email"],
        "first_name": current_user["first_name"],
        "last_name": current_user["last_name"],
        "risk_tolerance": current_user["risk_tolerance"]
    }

# ============== Stock Routes ==============

@app.get("/api/v1/stocks/quote/{symbol}", response_model=StockQuote)
async def get_stock_quote(symbol: str, current_user: dict = Depends(get_current_user)):
    """Get stock quote (MOCK DATA)."""
    quote = get_mock_quote(symbol.upper())
    if not quote:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found. Available: {', '.join(MOCK_STOCKS.keys())}")
    return quote

@app.get("/api/v1/stocks/batch")
async def get_batch_quotes(
    symbols: str = Query(..., description="Comma-separated symbols"),
    current_user: dict = Depends(get_current_user)
):
    """Get quotes for multiple stocks (MOCK DATA)."""
    symbol_list = [s.strip().upper() for s in symbols.split(",")][:10]
    quotes = []
    
    for symbol in symbol_list:
        quote = get_mock_quote(symbol)
        if quote:
            quotes.append(quote.model_dump())
    
    return {"quotes": quotes, "source": "mock_data"}

@app.get("/api/v1/stocks/search")
async def search_stocks(q: str, current_user: dict = Depends(get_current_user)):
    """Search for stocks."""
    query = q.upper()
    results = []
    for symbol, data in MOCK_STOCKS.items():
        if query in symbol or query.lower() in data["name"].lower():
            results.append({"symbol": symbol, "name": data["name"], "exchange": "NASDAQ"})
    return {"results": results[:5], "source": "mock_data"}

@app.get("/api/v1/stocks/available")
async def get_available_stocks(current_user: dict = Depends(get_current_user)):
    """Get list of available mock stocks."""
    return {
        "stocks": [{"symbol": s, "name": d["name"]} for s, d in MOCK_STOCKS.items()],
        "count": len(MOCK_STOCKS)
    }

# ============== AI Recommendations ==============

@app.get("/api/v1/recommendations", response_model=List[Recommendation])
async def get_recommendations(current_user: dict = Depends(get_current_user)):
    """Get AI-powered stock recommendations (MOCK DATA)."""
    recommendations = []
    
    stocks_to_analyze = [
        ("NVDA", "strong_buy", 0.92, "Strong AI infrastructure demand, dominant GPU market position"),
        ("AMZN", "buy", 0.87, "AWS growth acceleration, retail margin improvement"),
        ("META", "buy", 0.84, "Strong ad revenue recovery, AI integration driving engagement"),
    ]
    
    for symbol, rec_type, confidence, rationale in stocks_to_analyze:
        data = MOCK_STOCKS.get(symbol)
        if data:
            multiplier = 1.15 if rec_type == "strong_buy" else 1.10
            target_price = round(data["price"] * multiplier, 2)
            potential_return = round((target_price - data["price"]) / data["price"] * 100, 1)
            
            recommendations.append(Recommendation(
                id=f"{symbol}_rec_{datetime.utcnow().strftime('%Y%m%d')}",
                symbol=symbol,
                name=data["name"],
                recommendation_type=rec_type,
                confidence_score=confidence,
                current_price=data["price"],
                target_price=target_price,
                potential_return=potential_return,
                rationale=rationale
            ))
    
    return recommendations

# ============== Portfolio (Mock) ==============

@app.get("/api/v1/portfolio")
async def get_portfolio(current_user: dict = Depends(get_current_user)):
    """Get user portfolio (MOCK DATA)."""
    holdings = [
        {"symbol": "AAPL", "quantity": 50},
        {"symbol": "MSFT", "quantity": 25},
        {"symbol": "GOOGL", "quantity": 30},
    ]
    
    portfolio_holdings = []
    total_value = 0
    total_cost = 0
    day_gain = 0
    
    for h in holdings:
        data = MOCK_STOCKS.get(h["symbol"])
        if data:
            current_price = data["price"]
            avg_cost = current_price * 0.9  # Mock: bought at 10% lower
            value = h["quantity"] * current_price
            gain = (current_price - avg_cost) * h["quantity"]
            day_change = (current_price - data["prev_close"]) * h["quantity"]
            
            portfolio_holdings.append({
                "symbol": h["symbol"],
                "name": data["name"],
                "quantity": h["quantity"],
                "average_cost": round(avg_cost, 2),
                "current_price": round(current_price, 2),
                "total_value": round(value, 2),
                "gain": round(gain, 2),
                "gain_percent": round((gain / (h["quantity"] * avg_cost)) * 100, 2),
                "day_change": round(day_change, 2)
            })
            
            total_value += value
            total_cost += h["quantity"] * avg_cost
            day_gain += day_change
    
    total_gain = total_value - total_cost
    
    return {
        "total_value": round(total_value, 2),
        "total_gain": round(total_gain, 2),
        "total_gain_percent": round((total_gain / total_cost) * 100, 2) if total_cost > 0 else 0,
        "day_gain": round(day_gain, 2),
        "day_gain_percent": round((day_gain / (total_value - day_gain)) * 100, 2) if (total_value - day_gain) > 0 else 0,
        "holdings": portfolio_holdings,
        "last_updated": datetime.utcnow().isoformat(),
        "source": "mock_data"
    }

# ============== Watchlist (Mock) ==============

@app.get("/api/v1/watchlist")
async def get_watchlist(current_user: dict = Depends(get_current_user)):
    """Get user watchlist (MOCK DATA)."""
    watchlist_symbols = ["TSLA", "AMD", "INTC", "NFLX"]
    stocks = []
    
    for symbol in watchlist_symbols:
        quote = get_mock_quote(symbol)
        if quote:
            stocks.append(quote.model_dump())
    
    return {"name": "My Watchlist", "stocks": stocks, "source": "mock_data"}

# ============== Market Insights ==============

@app.get("/api/v1/insights")
async def get_market_insights(current_user: dict = Depends(get_current_user)):
    """Get market insights."""
    return {
        "insights": [
            {
                "id": "1",
                "title": "Fed Rate Decision Impact",
                "summary": "Markets rally following Federal Reserve's dovish stance on interest rates",
                "category": "economic_news",
                "impact": "high",
                "published_at": datetime.utcnow().isoformat()
            },
            {
                "id": "2",
                "title": "Tech Sector Outlook",
                "summary": "AI investments continue to drive tech sector growth in Q4",
                "category": "sector_analysis",
                "impact": "medium",
                "published_at": datetime.utcnow().isoformat()
            },
            {
                "id": "3",
                "title": "Earnings Season Preview",
                "summary": "Major tech companies report next week - what to expect",
                "category": "earnings_report",
                "impact": "high",
                "published_at": datetime.utcnow().isoformat()
            }
        ]
    }

# ============== Main ==============

if __name__ == "__main__":
    print("\n" + "="*60)
    print("    StockAdvisor Test Server (MOCK DATA)")
    print("="*60)
    print("Created by: Atul Shivade (atul.shivade@gmail.com)")
    print("-"*60)
    print("Server URL: http://localhost:8000")
    print("API Docs:   http://localhost:8000/docs")
    print("ReDoc:      http://localhost:8000/redoc")
    print("-"*60)
    print("NOTE: Using MOCK DATA (SSL/Proxy issues with live APIs)")
    print("-"*60)
    print("Test Steps:")
    print("  1. Open http://localhost:8000/docs in your browser")
    print("  2. Click 'Authorize' and login or register")
    print("  3. Test the endpoints")
    print("-"*60)
    print(f"Available Stocks: {', '.join(MOCK_STOCKS.keys())}")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
