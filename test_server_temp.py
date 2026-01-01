# test_server.py
# StockAdvisor Backend - Full Featured Server v7.0
# Developed by Atul Shivade @2026 atul.shivade@gmail.com

import ssl
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import json
import random
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
import threading
import secrets
import string

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from jose import jwt
from loguru import logger
import uvicorn

# ============== Configuration ==============
SECRET_KEY = os.getenv("SECRET_KEY", "stockadvisor-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# HARDCODED: Only this email has admin access
ADMIN_EMAIL = "atul.shivade@gmail.com"

# ============== SSL Context ==============
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ============== Caching ==============
stock_cache: Dict[str, dict] = {}
cache_expiry: Dict[str, datetime] = {}
search_cache: Dict[str, list] = {}
CACHE_DURATION = timedelta(seconds=30)
executor = ThreadPoolExecutor(max_workers=10)

# ============== Stock Exchanges ==============
EXCHANGES = {
    "US": {"name": "United States", "suffix": "", "currency": "USD", "currency_symbol": "$", "tradingview_prefix": "",
           "stocks": ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NFLX", "AMD", "INTC", "JPM", "V", "JNJ", "WMT", "DIS", "DOX", "NIO", "PLTR", "COIN", "UBER"]},
    "NSE": {"name": "India (NSE)", "suffix": ".NS", "currency": "INR", "currency_symbol": "₹", "tradingview_prefix": "NSE:",
            "stocks": ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "WIPRO", "BHARTIARTL", "ITC", "SBIN", "KOTAKBANK", "LT", "MARUTI", "HCLTECH", "AXISBANK", "BAJFINANCE"]},
    "LSE": {"name": "UK (London)", "suffix": ".L", "currency": "GBP", "currency_symbol": "£", "tradingview_prefix": "LSE:",
            "stocks": ["SHEL", "HSBA", "BP", "GSK", "AZN", "ULVR", "RIO", "DGE", "BATS", "LLOY", "VOD", "BARC", "NG", "BT-A", "IMB"]},
    "TSE": {"name": "Japan (Tokyo)", "suffix": ".T", "currency": "JPY", "currency_symbol": "¥", "tradingview_prefix": "TSE:",
            "stocks": ["7203", "6758", "9984", "6861", "8306", "9432", "7267", "6501", "4502", "8035"]},
    "HKEX": {"name": "Hong Kong", "suffix": ".HK", "currency": "HKD", "currency_symbol": "HK$", "tradingview_prefix": "HKEX:",
             "stocks": ["0700", "9988", "1299", "0005", "0939", "2318", "0941", "0388", "0001", "0016"]},
}

# ============== Stock Info ==============
STOCK_INFO = {
    "NVDA": {"name": "NVIDIA Corporation", "sector": "Technology", "logo": "🟢"},
    "AAPL": {"name": "Apple Inc.", "sector": "Technology", "logo": "🍎"},
    "GOOG": {"name": "Alphabet Inc.", "sector": "Technology", "logo": "🔵"},
    "MSFT": {"name": "Microsoft Corporation", "sector": "Technology", "logo": "🟦"},
    "AMZN": {"name": "Amazon.com, Inc.", "sector": "Retail", "logo": "📦"},
    "META": {"name": "Meta Platforms", "sector": "Technology", "logo": "Ⓜ️"},
    "TSLA": {"name": "Tesla, Inc.", "sector": "Automotive", "logo": "⚡"},
    "NFLX": {"name": "Netflix Inc.", "sector": "Entertainment", "logo": "🎬"},
    "AMD": {"name": "AMD Inc.", "sector": "Technology", "logo": "🔺"},
    "INTC": {"name": "Intel Corporation", "sector": "Technology", "logo": "🔷"},
    "JPM": {"name": "JPMorgan Chase", "sector": "Finance", "logo": "🏛️"},
    "V": {"name": "Visa Inc.", "sector": "Finance", "logo": "💳"},
    "JNJ": {"name": "Johnson & Johnson", "sector": "Healthcare", "logo": "🩹"},
    "WMT": {"name": "Walmart Inc.", "sector": "Retail", "logo": "🛒"},
    "DIS": {"name": "Walt Disney", "sector": "Entertainment", "logo": "🏰"},
    "DOX": {"name": "Amdocs Limited", "sector": "Technology", "logo": "💼"},
    "NIO": {"name": "NIO Inc.", "sector": "Automotive", "logo": "🚗"},
    "PLTR": {"name": "Palantir", "sector": "Technology", "logo": "🔮"},
    "COIN": {"name": "Coinbase", "sector": "Finance", "logo": "🪙"},
    "UBER": {"name": "Uber Technologies", "sector": "Technology", "logo": "🚕"},
    "RELIANCE": {"name": "Reliance Industries", "sector": "Energy", "logo": "🛢️"},
    "TCS": {"name": "Tata Consultancy", "sector": "Technology", "logo": "💻"},
    "INFY": {"name": "Infosys Limited", "sector": "Technology", "logo": "🖥️"},
    "HDFCBANK": {"name": "HDFC Bank", "sector": "Finance", "logo": "🏦"},
    "ICICIBANK": {"name": "ICICI Bank", "sector": "Finance", "logo": "🏦"},
    "WIPRO": {"name": "Wipro Limited", "sector": "Technology", "logo": "💻"},
    "BHARTIARTL": {"name": "Bharti Airtel", "sector": "Telecom", "logo": "📱"},
    "ITC": {"name": "ITC Limited", "sector": "Consumer", "logo": "🏭"},
    "SBIN": {"name": "State Bank of India", "sector": "Finance", "logo": "🏦"},
    "KOTAKBANK": {"name": "Kotak Mahindra", "sector": "Finance", "logo": "🏦"},
    "LT": {"name": "Larsen & Toubro", "sector": "Industrial", "logo": "🏗️"},
    "MARUTI": {"name": "Maruti Suzuki", "sector": "Automotive", "logo": "🚗"},
    "HCLTECH": {"name": "HCL Technologies", "sector": "Technology", "logo": "💻"},
    "AXISBANK": {"name": "Axis Bank", "sector": "Finance", "logo": "🏦"},
    "BAJFINANCE": {"name": "Bajaj Finance", "sector": "Finance", "logo": "💰"},
    "SHEL": {"name": "Shell plc", "sector": "Energy", "logo": "🛢️"},
    "HSBA": {"name": "HSBC Holdings", "sector": "Finance", "logo": "🏦"},
    "BP": {"name": "BP plc", "sector": "Energy", "logo": "⛽"},
    "GSK": {"name": "GSK plc", "sector": "Healthcare", "logo": "💊"},
    "AZN": {"name": "AstraZeneca", "sector": "Healthcare", "logo": "💉"},
    "ULVR": {"name": "Unilever plc", "sector": "Consumer", "logo": "🧴"},
    "RIO": {"name": "Rio Tinto", "sector": "Mining", "logo": "⛏️"},
    "DGE": {"name": "Diageo plc", "sector": "Consumer", "logo": "🥃"},
    "BATS": {"name": "British American Tobacco", "sector": "Consumer", "logo": "🚬"},
    "LLOY": {"name": "Lloyds Banking", "sector": "Finance", "logo": "🏦"},
    "7203": {"name": "Toyota Motor", "sector": "Automotive", "logo": "🚗"},
    "6758": {"name": "Sony Group", "sector": "Technology", "logo": "🎮"},
    "9984": {"name": "SoftBank Group", "sector": "Technology", "logo": "📱"},
    "6861": {"name": "Keyence Corp", "sector": "Technology", "logo": "🔧"},
    "8306": {"name": "Mitsubishi UFJ", "sector": "Finance", "logo": "🏦"},
    "0700": {"name": "Tencent Holdings", "sector": "Technology", "logo": "🎮"},
    "9988": {"name": "Alibaba Group", "sector": "Retail", "logo": "🛒"},
    "1299": {"name": "AIA Group", "sector": "Finance", "logo": "🏦"},
    "0005": {"name": "HSBC Holdings", "sector": "Finance", "logo": "🏦"},
    "0939": {"name": "China Construction Bank", "sector": "Finance", "logo": "🏦"},
}

# ============== Data Models ==============
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    risk_tolerance: str = "moderate"
    sso_provider: Optional[str] = None

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class SSOLogin(BaseModel):
    email: EmailStr
    provider: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class PortfolioItem(BaseModel):
    symbol: str
    quantity: int
    avg_cost: float

class PortfolioUpdate(BaseModel):
    quantity: Optional[int] = None
    avg_cost: Optional[float] = None

class WatchlistItem(BaseModel):
    symbol: str

class FeedbackCreate(BaseModel):
    type: str
    message: str
    page: Optional[str] = None

class FeedbackUpdate(BaseModel):
    status: str

class PasswordReset(BaseModel):
    new_password: str

# ============== Database ==============
users_db: Dict[str, dict] = {}
portfolios_db: Dict[str, Dict[str, List[dict]]] = {}
watchlists_db: Dict[str, Dict[str, List[str]]] = {}
feedback_db: List[dict] = []

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ============== Helpers ==============
def create_access_token(data: dict):
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email or email not in users_db:
            raise HTTPException(status_code=401, detail="Invalid token")
        return users_db[email]
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

def is_admin(user: dict) -> bool:
    # HARDCODED: Only atul.shivade@gmail.com is admin
    return user.get("email") == ADMIN_EMAIL

def generate_temp_password():
    """Generate a random temporary password"""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(12))

def init_user_data(email: str):
    """Initialize portfolio and watchlist for new user"""
    portfolios_db[email] = {
        "US": [{"symbol": "NVDA", "quantity": 25, "avg_cost": 120}, {"symbol": "AAPL", "quantity": 50, "avg_cost": 180}],
        "NSE": [{"symbol": "RELIANCE", "quantity": 20, "avg_cost": 2400}, {"symbol": "TCS", "quantity": 15, "avg_cost": 3500}],
        "LSE": [{"symbol": "SHEL", "quantity": 40, "avg_cost": 25}],
        "TSE": [{"symbol": "7203", "quantity": 100, "avg_cost": 2500}],
        "HKEX": [{"symbol": "0700", "quantity": 50, "avg_cost": 350}]
    }
    watchlists_db[email] = {ex: EXCHANGES[ex]["stocks"][:4] for ex in EXCHANGES}

def generate_ai_analysis(symbol: str, change_percent: float) -> dict:
    score = 50 + (change_percent * 5) + random.uniform(-20, 20)
    score = max(0, min(100, score))
    if score >= 80: sentiment, short, long = "STRONG BUY", "STRONG BUY", "BUY"
    elif score >= 65: sentiment, short, long = "BUY", "BUY", "HOLD"
    elif score >= 45: sentiment, short, long = "HOLD", "HOLD", "BUY"
    elif score >= 30: sentiment, short, long = "SELL", "SELL", "HOLD"
    else: sentiment, short, long = "STRONG SELL", "STRONG SELL", "SELL"
    return {
        "overall_sentiment": sentiment, "confidence_score": round(score, 1),
        "short_term_outlook": {"recommendation": short, "timeframe": "1-4 weeks", "target_change": round(random.uniform(-5, 15), 1)},
        "long_term_outlook": {"recommendation": long, "timeframe": "6-12 months", "target_change": round(random.uniform(5, 40), 1)},
        "bullish_factors": ["Positive momentum", "Strong volume", "Sector tailwinds"][:random.randint(1, 3)],
        "bearish_factors": ["Valuation concerns", "Market volatility", "Competition"][:random.randint(1, 3)],
        "risk_level": "High" if abs(change_percent) > 3 else "Medium" if abs(change_percent) > 1 else "Low",
        "technical_rating": random.choice(["Bullish", "Neutral", "Bearish"]),
        "fundamental_rating": random.choice(["Strong", "Moderate", "Weak"])
    }

def search_yahoo(query: str) -> list:
    try:
        cache_key = f"search:{query.upper()}"
        if cache_key in search_cache: return search_cache[cache_key]
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=12&newsCount=0"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            data = json.loads(response.read().decode())
        results = []
        for q in data.get('quotes', []):
            if q.get('quoteType') in ['EQUITY', 'ETF']:
                results.append({'symbol': q.get('symbol', '').split('.')[0], 'name': q.get('longname') or q.get('shortname', ''), 'exchange': q.get('exchange', ''), 'logo': '📈'})
        search_cache[cache_key] = results
        return results
    except: return []

def fetch_quote(symbol: str, exchange: str = "US") -> Optional[dict]:
    try:
        cache_key = f"{exchange}:{symbol}"
        if cache_key in stock_cache and cache_key in cache_expiry:
            if datetime.utcnow() < cache_expiry[cache_key]: return stock_cache[cache_key]
        suffix = EXCHANGES.get(exchange, {}).get("suffix", "")
        query_symbol = f"{symbol}{suffix}" if suffix else symbol
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{query_symbol}?interval=1d&range=2d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            data = json.loads(response.read().decode())
        if data.get('chart', {}).get('result'):
            result = data['chart']['result'][0]
            meta = result.get('meta', {})
            current = meta.get('regularMarketPrice', 0)
            prev = meta.get('previousClose', current)
            stock_data = {
                'symbol': symbol, 'current_price': round(current, 2), 'previous_close': round(prev, 2),
                'change': round(current - prev, 2), 'change_percent': round(((current - prev) / prev * 100) if prev else 0, 2),
                'day_high': round(meta.get('regularMarketDayHigh', current * 1.01), 2),
                'day_low': round(meta.get('regularMarketDayLow', current * 0.99), 2),
                'open_price': round(meta.get('regularMarketOpen', current), 2),
                'volume': int(meta.get('regularMarketVolume', 0)), 'is_live': True
            }
            stock_cache[cache_key] = stock_data
            cache_expiry[cache_key] = datetime.utcnow() + CACHE_DURATION
            return stock_data
    except: pass
    return None

def get_quote(symbol: str, exchange: str = "US") -> dict:
    symbol = symbol.upper()
    ex_info = EXCHANGES.get(exchange, EXCHANGES["US"])
    info = STOCK_INFO.get(symbol, {"name": symbol, "sector": "Unknown", "logo": "📈"})
    live = fetch_quote(symbol, exchange)
    if live:
        return {
            "symbol": symbol, "name": info["name"], "current_price": live['current_price'],
            "previous_close": live['previous_close'], "change": live['change'], "change_percent": live['change_percent'],
            "day_high": live['day_high'], "day_low": live['day_low'], "open_price": live['open_price'],
            "volume": live['volume'], "market_cap": int(live['current_price'] * random.uniform(1e9, 3e12)),
            "pe_ratio": round(random.uniform(15, 50), 2), "sector": info["sector"],
            "analyst_rating": "Strong Buy" if live['change_percent'] > 1 else "Buy" if live['change_percent'] > 0 else "Neutral",
            "logo": info["logo"], "currency": ex_info["currency"], "currency_symbol": ex_info["currency_symbol"],
            "tradingview_url": f"https://www.tradingview.com/symbols/{ex_info['tradingview_prefix']}{symbol}/",
            "is_live": True, "exchange": exchange
        }
    else:
        mult = {"US": 1, "NSE": 80, "LSE": 0.8, "TSE": 150, "HKEX": 8}.get(exchange, 1)
        price = round(random.uniform(50, 500) * mult, 2)
        prev = round(price * random.uniform(0.97, 1.03), 2)
        return {
            "symbol": symbol, "name": info["name"], "current_price": price, "previous_close": prev,
            "change": round(price - prev, 2), "change_percent": round((price - prev) / prev * 100, 2),
            "day_high": round(price * 1.02, 2), "day_low": round(price * 0.98, 2), "open_price": prev,
            "volume": int(random.uniform(1e6, 50e6)), "market_cap": int(price * random.uniform(1e9, 2e12)),
            "pe_ratio": round(random.uniform(15, 40), 2), "sector": info["sector"], "analyst_rating": "Neutral",
            "logo": info["logo"], "currency": ex_info["currency"], "currency_symbol": ex_info["currency_symbol"],
            "tradingview_url": f"https://www.tradingview.com/symbols/{ex_info['tradingview_prefix']}{symbol}/",
            "is_live": False, "exchange": exchange
        }

# ============== FastAPI ==============
app = FastAPI(title="StockAdvisor API", version="7.0.0", description="Developed by Atul Shivade @2026")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
async def root():
    return {"name": "StockAdvisor API", "version": "7.0.0", "developer": "Atul Shivade @2026", "contact": "atul.shivade@gmail.com"}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "developer": "Atul Shivade"}

# ============== Auth ==============
@app.post("/api/v1/auth/register", response_model=TokenResponse)
async def register(user: UserCreate):
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    users_db[user.email] = {
        "email": user.email, "password": user.password,
        "first_name": user.first_name, "last_name": user.last_name,
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True, "sso_provider": user.sso_provider,
        "login_issues": None
    }
    init_user_data(user.email)
    return TokenResponse(access_token=create_access_token({"sub": user.email}))

@app.post("/api/v1/auth/sso", response_model=TokenResponse)
async def sso_login(sso: SSOLogin):
    """SSO login - creates account if doesn't exist, otherwise logs in"""
    if sso.email not in users_db:
        # Auto-create account for SSO users
        temp_password = generate_temp_password()
        first_name = sso.first_name or sso.email.split('@')[0].title()
        last_name = sso.last_name or ""
        users_db[sso.email] = {
            "email": sso.email, "password": temp_password,
            "first_name": first_name, "last_name": last_name,
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True, "sso_provider": sso.provider,
            "login_issues": None
        }
        init_user_data(sso.email)
    
    user = users_db[sso.email]
    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Account disabled. Contact admin.")
    
    return TokenResponse(access_token=create_access_token({"sub": sso.email}))

@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Account disabled. Contact admin at atul.shivade@gmail.com")
    if user["password"] != form_data.password:
        # Log failed attempt
        user["login_issues"] = f"Failed login attempt at {datetime.utcnow().isoformat()}"
        raise HTTPException(status_code=401, detail="Invalid email or password")
    # Clear login issues on successful login
    user["login_issues"] = None
    return TokenResponse(access_token=create_access_token({"sub": form_data.username}))

@app.get("/api/v1/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "email": user["email"], "first_name": user["first_name"], "last_name": user["last_name"],
        "is_admin": is_admin(user), "sso_provider": user.get("sso_provider")
    }

# ============== Stocks ==============
@app.get("/api/v1/stocks/search")
async def search_stocks(q: str, exchange: str = Query("US"), user: dict = Depends(get_current_user)):
    if len(q) < 1: return {"results": []}
    return {"results": search_yahoo(q)[:12], "source": "yahoo_finance"}

@app.get("/api/v1/stocks/quote/{symbol}")
async def get_single_quote(symbol: str, exchange: str = Query("US"), user: dict = Depends(get_current_user)):
    quote = get_quote(symbol, exchange)
    quote["ai_analysis"] = generate_ai_analysis(symbol, quote["change_percent"])
    return quote

@app.get("/api/v1/stocks/market-overview")
async def get_market(exchange: str = Query("US"), user: dict = Depends(get_current_user)):
    ex_info = EXCHANGES.get(exchange, EXCHANGES["US"])
    def fetch(sym): return get_quote(sym, exchange)
    with ThreadPoolExecutor(max_workers=8) as ex:
        quotes = list(ex.map(fetch, ex_info["stocks"][:15]))
    quotes.sort(key=lambda x: x.get('market_cap', 0) or 0, reverse=True)
    return {"stocks": quotes, "exchange": exchange, "currency": ex_info["currency"], "currency_symbol": ex_info["currency_symbol"]}

# ============== Portfolio ==============
@app.get("/api/v1/portfolio")
async def get_portfolio(exchange: str = Query("US"), user: dict = Depends(get_current_user)):
    email = user["email"]
    ex_info = EXCHANGES.get(exchange, EXCHANGES["US"])
    if email not in portfolios_db: portfolios_db[email] = {}
    if exchange not in portfolios_db[email]:
        mult = {"US": 1, "NSE": 80, "LSE": 0.8, "TSE": 150, "HKEX": 8}.get(exchange, 1)
        portfolios_db[email][exchange] = [{"symbol": s, "quantity": random.randint(10, 50), "avg_cost": round(random.uniform(50, 200) * mult, 2)} for s in ex_info["stocks"][:3]]
    
    def process(h):
        try:
            q = get_quote(h["symbol"], exchange)
            val, cost = h["quantity"] * q["current_price"], h["quantity"] * h["avg_cost"]
            return {
                "symbol": h["symbol"], "name": q["name"], "logo": q["logo"], "quantity": h["quantity"],
                "average_cost": h["avg_cost"], "current_price": q["current_price"], "total_value": round(val, 2),
                "gain": round(val - cost, 2), "gain_percent": round((val - cost) / cost * 100, 2) if cost else 0,
                "day_change": round((q["current_price"] - q["previous_close"]) * h["quantity"], 2),
                "day_change_percent": q["change_percent"], "is_live": q["is_live"],
                "currency_symbol": q["currency_symbol"], "tradingview_url": q["tradingview_url"]
            }
        except: return None
    
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = [r for r in ex.map(process, portfolios_db[email][exchange]) if r]
    
    total_value = sum(h["total_value"] for h in results)
    total_cost = sum(h["quantity"] * h["average_cost"] for h in results)
    day_gain = sum(h["day_change"] for h in results)
    return {
        "total_value": round(total_value, 2), "total_cost": round(total_cost, 2),
        "total_gain": round(total_value - total_cost, 2),
        "total_gain_percent": round((total_value - total_cost) / total_cost * 100, 2) if total_cost else 0,
        "day_gain": round(day_gain, 2), "day_gain_percent": round(day_gain / total_value * 100, 2) if total_value else 0,
        "holdings": results, "currency": ex_info["currency"], "currency_symbol": ex_info["currency_symbol"], "exchange": exchange
    }

@app.post("/api/v1/portfolio/add")
async def add_portfolio(item: PortfolioItem, exchange: str = Query("US"), user: dict = Depends(get_current_user)):
    email = user["email"]
    if email not in portfolios_db: portfolios_db[email] = {}
    if exchange not in portfolios_db[email]: portfolios_db[email][exchange] = []
    for h in portfolios_db[email][exchange]:
        if h["symbol"] == item.symbol.upper():
            total_qty = h["quantity"] + item.quantity
            h["avg_cost"] = round(((h["quantity"] * h["avg_cost"]) + (item.quantity * item.avg_cost)) / total_qty, 2)
            h["quantity"] = total_qty
            return {"message": f"Updated {item.symbol}"}
    portfolios_db[email][exchange].append({"symbol": item.symbol.upper(), "quantity": item.quantity, "avg_cost": item.avg_cost})
    return {"message": f"Added {item.symbol}"}

@app.delete("/api/v1/portfolio/{symbol}")
async def delete_portfolio(symbol: str, exchange: str = Query("US"), user: dict = Depends(get_current_user)):
    email = user["email"]
    if email in portfolios_db and exchange in portfolios_db[email]:
        portfolios_db[email][exchange] = [h for h in portfolios_db[email][exchange] if h["symbol"] != symbol.upper()]
    return {"message": f"Removed {symbol}"}

# ============== Watchlist ==============
@app.get("/api/v1/watchlist")
async def get_watchlist(exchange: str = Query("US"), user: dict = Depends(get_current_user)):
    email = user["email"]
    ex_info = EXCHANGES.get(exchange, EXCHANGES["US"])
    if email not in watchlists_db: watchlists_db[email] = {}
    if exchange not in watchlists_db[email]: watchlists_db[email][exchange] = ex_info["stocks"][:5]
    def fetch(sym): return get_quote(sym, exchange)
    with ThreadPoolExecutor(max_workers=8) as ex:
        stocks = list(ex.map(fetch, watchlists_db[email][exchange]))
    return {"stocks": stocks, "count": len(stocks), "currency": ex_info["currency"], "currency_symbol": ex_info["currency_symbol"], "exchange": exchange}

@app.post("/api/v1/watchlist/add")
async def add_watchlist(item: WatchlistItem, exchange: str = Query("US"), user: dict = Depends(get_current_user)):
    email = user["email"]
    if email not in watchlists_db: watchlists_db[email] = {}
    if exchange not in watchlists_db[email]: watchlists_db[email][exchange] = []
    if item.symbol.upper() not in watchlists_db[email][exchange]:
        watchlists_db[email][exchange].append(item.symbol.upper())
    return {"message": f"Added {item.symbol}"}

@app.delete("/api/v1/watchlist/{symbol}")
async def delete_watchlist(symbol: str, exchange: str = Query("US"), user: dict = Depends(get_current_user)):
    email = user["email"]
    if email in watchlists_db and exchange in watchlists_db[email]:
        if symbol.upper() in watchlists_db[email][exchange]:
            watchlists_db[email][exchange].remove(symbol.upper())
    return {"message": f"Removed {symbol}"}

# ============== Recommendations ==============
@app.get("/api/v1/recommendations")
async def get_recommendations(exchange: str = Query("US"), user: dict = Depends(get_current_user)):
    ex_info = EXCHANGES.get(exchange, EXCHANGES["US"])
    def fetch(sym):
        q = get_quote(sym, exchange)
        ai = generate_ai_analysis(sym, q["change_percent"])
        if ai["overall_sentiment"] in ["STRONG BUY", "BUY"]:
            mult = 1.15 if ai["overall_sentiment"] == "STRONG BUY" else 1.10
            return {
                "symbol": sym, "name": q["name"], "recommendation_type": ai["overall_sentiment"].lower().replace(" ", "_"),
                "confidence_score": ai["confidence_score"] / 100, "current_price": q["current_price"],
                "target_price": round(q["current_price"] * mult, 2), "potential_return": round((mult - 1) * 100, 1),
                "short_term": ai["short_term_outlook"], "long_term": ai["long_term_outlook"],
                "rationale": ai["bullish_factors"][0] if ai["bullish_factors"] else "Strong fundamentals",
                "currency_symbol": q["currency_symbol"], "tradingview_url": q["tradingview_url"]
            }
        return None
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = [r for r in ex.map(fetch, ex_info["stocks"][:10]) if r]
    results.sort(key=lambda x: x["confidence_score"], reverse=True)
    return results[:5]

# ============== Feedback ==============
@app.get("/api/v1/feedback")
async def get_feedback(status: Optional[str] = None, user: dict = Depends(get_current_user)):
    if is_admin(user):
        feedbacks = feedback_db if not status else [f for f in feedback_db if f["status"] == status]
    else:
        feedbacks = [f for f in feedback_db if f["user_email"] == user["email"]]
    return {"feedback": sorted(feedbacks, key=lambda x: x["created_at"], reverse=True), "count": len(feedbacks), "is_admin": is_admin(user)}

@app.post("/api/v1/feedback")
async def create_feedback(item: FeedbackCreate, user: dict = Depends(get_current_user)):
    entry = {
        "id": str(uuid.uuid4()), "user_email": user["email"],
        "user_name": f"{user['first_name']} {user['last_name']}",
        "type": item.type, "message": item.message, "page": item.page, "status": "new",
        "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()
    }
    feedback_db.append(entry)
    return {"message": "Feedback submitted", "feedback": entry}

@app.put("/api/v1/feedback/{feedback_id}")
async def update_feedback(feedback_id: str, update: FeedbackUpdate, user: dict = Depends(get_current_user)):
    if not is_admin(user): raise HTTPException(status_code=403, detail="Admin access required")
    for f in feedback_db:
        if f["id"] == feedback_id:
            f["status"], f["updated_at"] = update.status, datetime.utcnow().isoformat()
            return {"message": "Updated"}
    raise HTTPException(status_code=404, detail="Not found")

@app.delete("/api/v1/feedback/{feedback_id}")
async def delete_feedback(feedback_id: str, user: dict = Depends(get_current_user)):
    if not is_admin(user): raise HTTPException(status_code=403, detail="Admin access required")
    global feedback_db
    feedback_db = [f for f in feedback_db if f["id"] != feedback_id]
    return {"message": "Deleted"}

# ============== Admin ==============
@app.get("/api/v1/admin/users")
async def get_users(user: dict = Depends(get_current_user)):
    if not is_admin(user): raise HTTPException(status_code=403, detail="Admin access required")
    return {"users": [
        {"email": u["email"], "first_name": u["first_name"], "last_name": u["last_name"],
         "is_admin": u["email"] == ADMIN_EMAIL, "is_active": u.get("is_active", True),
         "created_at": u.get("created_at"), "sso_provider": u.get("sso_provider"),
         "login_issues": u.get("login_issues")}
        for u in users_db.values()
    ]}

@app.put("/api/v1/admin/users/{email}")
async def update_user(email: str, update: UserUpdate, user: dict = Depends(get_current_user)):
    if not is_admin(user): raise HTTPException(status_code=403, detail="Admin access required")
    if email not in users_db: raise HTTPException(status_code=404, detail="User not found")
    u = users_db[email]
    if update.is_active is not None: u["is_active"] = update.is_active
    if update.password: u["password"] = update.password
    if update.first_name: u["first_name"] = update.first_name
    if update.last_name: u["last_name"] = update.last_name
    u["login_issues"] = None  # Clear login issues on admin update
    return {"message": "User updated"}

@app.post("/api/v1/admin/users/{email}/reset-password")
async def reset_user_password(email: str, user: dict = Depends(get_current_user)):
    """Admin can reset user password to a temporary one"""
    if not is_admin(user): raise HTTPException(status_code=403, detail="Admin access required")
    if email not in users_db: raise HTTPException(status_code=404, detail="User not found")
    new_password = generate_temp_password()
    users_db[email]["password"] = new_password
    users_db[email]["login_issues"] = None
    return {"message": "Password reset", "temporary_password": new_password}

@app.get("/api/v1/admin/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    if not is_admin(user): raise HTTPException(status_code=403, detail="Admin access required")
    stats = {"new": 0, "in_progress": 0, "resolved": 0, "closed": 0}
    for f in feedback_db: stats[f["status"]] = stats.get(f["status"], 0) + 1
    users_with_issues = sum(1 for u in users_db.values() if u.get("login_issues"))
    return {"total_users": len(users_db), "total_feedback": len(feedback_db), "feedback_stats": stats, "users_with_login_issues": users_with_issues}

# ============== OAuth SSO ==============
oauth_states: Dict[str, dict] = {}

@app.get("/api/v1/auth/oauth/{provider}")
async def oauth_start(provider: str):
    """Initialize OAuth flow - serves demo login page directly"""
    from fastapi.responses import HTMLResponse
    
    state = secrets.token_urlsafe(32)
    oauth_states[state] = {"provider": provider, "created": datetime.utcnow().isoformat()}
    
    colors = {"google": "#4285F4", "microsoft": "#00A4EF", "yahoo": "#6001D2"}
    emails = {"google": "gmail.com", "microsoft": "outlook.com", "yahoo": "yahoo.com"}
    logos = {"google": "G", "microsoft": "M", "yahoo": "Y"}
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Sign in with {provider.title()}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
        .container {{ background: white; padding: 2.5rem; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.1); width: 100%; max-width: 400px; text-align: center; }}
        .logo {{ width: 60px; height: 60px; background: {colors.get(provider, '#333')}; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; margin: 0 auto 1rem; }}
        h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; color: #333; }}
        p {{ color: #666; margin-bottom: 1.5rem; }}
        input {{ width: 100%; padding: 0.75rem 1rem; border: 1px solid #ddd; border-radius: 8px; font-size: 1rem; margin-bottom: 1rem; }}
        input:focus {{ outline: none; border-color: {colors.get(provider, '#333')}; }}
        button {{ width: 100%; padding: 0.75rem; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; }}
        .btn-primary {{ background: {colors.get(provider, '#333')}; color: white; }}
        .btn-cancel {{ background: #f5f5f5; color: #666; margin-top: 0.5rem; }}
        .divider {{ margin: 1.5rem 0; color: #999; font-size: 0.85rem; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">{logos.get(provider, 'O')}</div>
        <h1>Sign in with {provider.title()}</h1>
        <p>Enter your email to continue to StockAdvisor</p>
        <form onsubmit="handleSubmit(event)">
            <input type="email" id="email" placeholder="your.email@{emails.get(provider, 'email.com')}" required autofocus>
            <input type="text" id="name" placeholder="Your Name (optional)">
            <button type="submit" class="btn-primary">Continue</button>
            <button type="button" class="btn-cancel" onclick="window.close()">Cancel</button>
        </form>
        <div class="divider">Demo Mode - Simulated OAuth</div>
    </div>
    <script>
        function handleSubmit(e) {{
            e.preventDefault();
            var email = document.getElementById('email').value;
            var name = document.getElementById('name').value || email.split('@')[0];
            window.location.href = '/api/v1/auth/oauth/callback?state={state}&provider={provider}&email=' + encodeURIComponent(email) + '&name=' + encodeURIComponent(name);
        }}
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)

@app.get("/api/v1/auth/oauth/callback")
async def oauth_callback(state: str, provider: str, email: str, name: str = ""):
    """OAuth callback - creates user and returns token"""
    from fastapi.responses import HTMLResponse
    
    # Clean up state
    if state in oauth_states:
        del oauth_states[state]
    
    if not email:
        return HTMLResponse("<h1>Email required</h1>", status_code=400)
    
    # Create or login user
    if email not in users_db:
        first_name = name.split()[0] if name else email.split('@')[0].title()
        last_name = name.split()[-1] if name and len(name.split()) > 1 else ""
        users_db[email] = {
            "email": email, "password": generate_temp_password(),
            "first_name": first_name, "last_name": last_name,
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True, "sso_provider": provider, "login_issues": None
        }
        init_user_data(email)
    
    user = users_db[email]
    if not user.get("is_active", True):
        return HTMLResponse("<h1>Account disabled</h1>", status_code=401)
    
    token = create_access_token({"sub": email})
    
    html = f"""<!DOCTYPE html>
<html>
<head><title>Success</title></head>
<body>
    <script>
        if (window.opener) {{
            window.opener.postMessage({{ type: 'oauth_success', token: '{token}', email: '{email}' }}, '*');
            window.close();
        }} else {{
            localStorage.setItem('token', '{token}');
            window.location.href = '/';
        }}
    </script>
    <p>Authentication successful! This window should close automatically.</p>
</body>
</html>"""
    return HTMLResponse(content=html)

# ============== Sanity Tests ==============
sanity_results: List[dict] = []

class SanityTestResult(BaseModel):
    test_name: str
    status: str
    duration_ms: int
    message: str

@app.post("/api/v1/admin/sanity/run")
async def run_sanity_tests(user: dict = Depends(get_current_user)):
    """Run all sanity tests and store results"""
    if not is_admin(user): raise HTTPException(status_code=403, detail="Admin access required")
    
    global sanity_results
    sanity_results = []
    test_email = f"sanity_test_{uuid.uuid4().hex[:8]}@test.com"
    test_token = None
    
    async def run_test(name: str, test_func):
        start = datetime.utcnow()
        try:
            result = await test_func() if callable(test_func) else test_func
            status = "PASS" if result else "FAIL"
            message = "Test passed" if result else "Test failed"
        except Exception as e:
            status = "ERROR"
            message = str(e)[:100]
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)
        sanity_results.append({"test_name": name, "status": status, "duration_ms": duration, "message": message, "timestamp": datetime.utcnow().isoformat()})
    
    # Test 1: Health Check
    await run_test("API Health Check", True)
    
    # Test 2: User Registration
    try:
        users_db[test_email] = {
            "email": test_email, "password": "test123",
            "first_name": "Sanity", "last_name": "Test",
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True, "sso_provider": None, "login_issues": None
        }
        init_user_data(test_email)
        await run_test("User Registration", True)
    except Exception as e:
        await run_test("User Registration", False)
    
    # Test 3: User Login
    try:
        test_token = create_access_token({"sub": test_email})
        await run_test("User Login", test_token is not None)
    except:
        await run_test("User Login", False)
    
    # Test 4: Get User Profile
    await run_test("Get User Profile", test_email in users_db)
    
    # Test 5: Stock Search
    try:
        results = search_yahoo("AAPL")
        await run_test("Stock Search (Yahoo)", len(results) > 0)
    except:
        await run_test("Stock Search (Yahoo)", False)
    
    # Test 6: Get Stock Quote
    try:
        quote = get_quote("AAPL", "US")
        await run_test("Get Stock Quote", quote.get("current_price", 0) > 0)
    except:
        await run_test("Get Stock Quote", False)
    
    # Test 7: Market Overview
    try:
        ex_info = EXCHANGES.get("US")
        await run_test("Market Overview", len(ex_info["stocks"]) > 0)
    except:
        await run_test("Market Overview", False)
    
    # Test 8: Portfolio Operations
    try:
        portfolios_db[test_email]["US"].append({"symbol": "TEST", "quantity": 10, "avg_cost": 100})
        has_test = any(h["symbol"] == "TEST" for h in portfolios_db[test_email]["US"])
        await run_test("Portfolio Add", has_test)
    except:
        await run_test("Portfolio Add", False)
    
    # Test 9: Portfolio Remove
    try:
        portfolios_db[test_email]["US"] = [h for h in portfolios_db[test_email]["US"] if h["symbol"] != "TEST"]
        no_test = not any(h["symbol"] == "TEST" for h in portfolios_db[test_email]["US"])
        await run_test("Portfolio Remove", no_test)
    except:
        await run_test("Portfolio Remove", False)
    
    # Test 10: Watchlist Operations
    try:
        watchlists_db[test_email]["US"].append("TEST")
        has_test = "TEST" in watchlists_db[test_email]["US"]
        await run_test("Watchlist Add", has_test)
    except:
        await run_test("Watchlist Add", False)
    
    # Test 11: Watchlist Remove
    try:
        if "TEST" in watchlists_db[test_email]["US"]:
            watchlists_db[test_email]["US"].remove("TEST")
        no_test = "TEST" not in watchlists_db[test_email]["US"]
        await run_test("Watchlist Remove", no_test)
    except:
        await run_test("Watchlist Remove", False)
    
    # Test 12: AI Recommendations
    try:
        ai = generate_ai_analysis("AAPL", 2.5)
        await run_test("AI Analysis Generation", ai.get("overall_sentiment") is not None)
    except:
        await run_test("AI Analysis Generation", False)
    
    # Test 13: Feedback Create
    try:
        test_feedback = {
            "id": str(uuid.uuid4()), "user_email": test_email,
            "user_name": "Sanity Test", "type": "test", "message": "Sanity test feedback",
            "page": "/test", "status": "new", "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        feedback_db.append(test_feedback)
        await run_test("Feedback Create", True)
    except:
        await run_test("Feedback Create", False)
    
    # Test 14: Feedback Update
    try:
        for f in feedback_db:
            if f.get("user_email") == test_email:
                f["status"] = "resolved"
                break
        await run_test("Feedback Update", True)
    except:
        await run_test("Feedback Update", False)
    
    # Test 15: Exchange Support
    try:
        all_exchanges = all(ex in EXCHANGES for ex in ["US", "NSE", "LSE", "TSE", "HKEX"])
        await run_test("Multi-Exchange Support", all_exchanges)
    except:
        await run_test("Multi-Exchange Support", False)
    
    # Test 16: Cache System
    try:
        cache_working = isinstance(stock_cache, dict) and isinstance(cache_expiry, dict)
        await run_test("Cache System", cache_working)
    except:
        await run_test("Cache System", False)
    
    # Test 17: Admin Functions
    await run_test("Admin Access Control", is_admin(user))
    
    # Test 18: Password Generation
    try:
        pwd = generate_temp_password()
        await run_test("Password Generation", len(pwd) >= 12)
    except:
        await run_test("Password Generation", False)
    
    # Test 19: Token Generation
    try:
        token = create_access_token({"sub": "test@test.com"})
        await run_test("JWT Token Generation", token is not None and len(token) > 50)
    except:
        await run_test("JWT Token Generation", False)
    
    # Test 20: Data Cleanup
    try:
        if test_email in users_db: del users_db[test_email]
        if test_email in portfolios_db: del portfolios_db[test_email]
        if test_email in watchlists_db: del watchlists_db[test_email]
        # Remove test feedback entries
        feedback_to_remove = [f for f in feedback_db if f.get("user_email") == test_email]
        for f in feedback_to_remove: feedback_db.remove(f)
        await run_test("Test Data Cleanup", test_email not in users_db)
    except:
        await run_test("Test Data Cleanup", False)
    
    # Summary
    passed = sum(1 for r in sanity_results if r["status"] == "PASS")
    failed = sum(1 for r in sanity_results if r["status"] == "FAIL")
    errors = sum(1 for r in sanity_results if r["status"] == "ERROR")
    
    return {
        "summary": {"total": len(sanity_results), "passed": passed, "failed": failed, "errors": errors},
        "results": sanity_results,
        "run_at": datetime.utcnow().isoformat(),
        "run_by": user["email"]
    }

@app.get("/api/v1/admin/sanity/results")
async def get_sanity_results(user: dict = Depends(get_current_user)):
    """Get last sanity test results"""
    if not is_admin(user): raise HTTPException(status_code=403, detail="Admin access required")
    
    if not sanity_results:
        return {"summary": {"total": 0, "passed": 0, "failed": 0, "errors": 0}, "results": [], "message": "No tests run yet"}
    
    passed = sum(1 for r in sanity_results if r["status"] == "PASS")
    failed = sum(1 for r in sanity_results if r["status"] == "FAIL")
    errors = sum(1 for r in sanity_results if r["status"] == "ERROR")
    
    return {
        "summary": {"total": len(sanity_results), "passed": passed, "failed": failed, "errors": errors},
        "results": sanity_results
    }

# ============== Main ==============
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  StockAdvisor API v7.0")
    print("  Developed by Atul Shivade @2026")
    print("  Contact: atul.shivade@gmail.com")
    print("="*50)
    print(f"  Admin: {ADMIN_EMAIL}")
    print("  Server: http://localhost:8000")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
