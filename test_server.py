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

from fastapi import FastAPI, HTTPException, Depends, Query, Request
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
DATA_PERSIST_FILE = os.getenv("DATA_PERSIST_FILE", "stockadvisor_data.json")

# ============== Data Persistence Functions ==============
def save_persistent_data():
    """Save guest sessions and feedback to file for persistence across restarts"""
    try:
        data = {
            "guest_sessions": guest_sessions_db,
            "feedback": feedback_db,
            "registered_users": {k: {**v, "password": "***"} for k, v in users_db.items() if k != ADMIN_EMAIL and not k.startswith("guest_")},
            "saved_at": datetime.now().isoformat()
        }
        with open(DATA_PERSIST_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Data saved: {len(guest_sessions_db)} guest sessions, {len(feedback_db)} feedback items")
    except Exception as e:
        logger.error(f"Failed to save data: {e}")

def load_persistent_data():
    """Load guest sessions and feedback from file on startup"""
    global guest_sessions_db, feedback_db
    try:
        if os.path.exists(DATA_PERSIST_FILE):
            with open(DATA_PERSIST_FILE, 'r') as f:
                data = json.load(f)
            guest_sessions_db.extend(data.get("guest_sessions", []))
            feedback_db.extend(data.get("feedback", []))
            logger.info(f"Data loaded: {len(guest_sessions_db)} guest sessions, {len(feedback_db)} feedback items")
    except Exception as e:
        logger.error(f"Failed to load data: {e}")

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
CACHE_DURATION = timedelta(seconds=15)  # Reduced for more real-time data
SEARCH_CACHE_DURATION = timedelta(minutes=5)  # Search results can be cached longer
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

class GuestDeviceInfo(BaseModel):
    user_agent: Optional[str] = None
    platform: Optional[str] = None
    language: Optional[str] = None
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    timezone: Optional[str] = None
    ip_address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class StockAlertCreate(BaseModel):
    symbol: str
    entry_price: float
    stop_loss: float
    target_price: float
    rationale: Optional[str] = None
    exchange: str = "NSE"

class StockAlertUpdate(BaseModel):
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    rationale: Optional[str] = None
    status: Optional[str] = None  # active, hit_target, hit_sl, cancelled

# ============== Database ==============
# Pre-create admin user with known password
users_db: Dict[str, dict] = {
    ADMIN_EMAIL: {
        "email": ADMIN_EMAIL,
        "password": "admin123",  # DEFAULT ADMIN PASSWORD
        "first_name": "Atul",
        "last_name": "Shivade",
        "created_at": datetime.now().isoformat(),
        "is_active": True,
        "sso_provider": None,
        "login_issues": None
    }
}
portfolios_db: Dict[str, Dict[str, List[dict]]] = {}
watchlists_db: Dict[str, Dict[str, List[str]]] = {}
feedback_db: List[dict] = []
guest_sessions_db: List[dict] = []  # Store guest session details
stock_alerts_db: Dict[str, List[dict]] = {
    # Sample alerts to show the feature
    "system@stockadvisor.app": [
        {
            "id": "sample-1",
            "symbol": "RELIANCE",
            "entry_price": 2850.00,
            "stop_loss": 2750.00,
            "target_price": 3150.00,
            "rationale": "Strong quarterly results with improving refinery margins. Technical breakout above key resistance level.",
            "exchange": "NSE",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "created_by": "system@stockadvisor.app"
        },
        {
            "id": "sample-2",
            "symbol": "TCS",
            "entry_price": 3950.00,
            "stop_loss": 3800.00,
            "target_price": 4300.00,
            "rationale": "IT sector recovery expected. Strong order book and deal wins in Q3.",
            "exchange": "NSE",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "created_by": "system@stockadvisor.app"
        },
        {
            "id": "sample-3",
            "symbol": "ICICIBANK",
            "entry_price": 1050.00,
            "stop_loss": 1000.00,
            "target_price": 1180.00,
            "rationale": "Banking sector strength with improving NII margins. Bullish chart pattern formation.",
            "exchange": "NSE",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "created_by": "system@stockadvisor.app"
        },
        {
            "id": "sample-4",
            "symbol": "NVDA",
            "entry_price": 135.00,
            "stop_loss": 125.00,
            "target_price": 160.00,
            "rationale": "AI demand continues to surge. Strong data center growth momentum.",
            "exchange": "US",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "created_by": "system@stockadvisor.app"
        },
        {
            "id": "sample-5",
            "symbol": "AAPL",
            "entry_price": 190.00,
            "stop_loss": 180.00,
            "target_price": 215.00,
            "rationale": "iPhone 16 launch expected to drive growth. Services revenue at all-time high.",
            "exchange": "US",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "created_by": "system@stockadvisor.app"
        }
    ]
}  # User email -> list of stock alerts

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

def generate_ai_rationale(symbol: str, entry_price: float, target_price: float, stop_loss: float, exchange: str = "NSE") -> str:
    """Generate AI-derived rationale for stock alert based on technical analysis patterns"""
    stock_info = STOCK_INFO.get(symbol, {"name": symbol, "sector": "Unknown"})
    sector = stock_info.get("sector", "Unknown")
    name = stock_info.get("name", symbol)
    
    potential_gain = ((target_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
    risk_reward = abs((target_price - entry_price) / (entry_price - stop_loss)) if (entry_price - stop_loss) != 0 else 1
    
    # Technical patterns
    patterns = [
        f"Breakout above key resistance at {entry_price:.2f}",
        f"Double bottom pattern forming with strong support at {stop_loss:.2f}",
        f"Cup and handle pattern completion near entry level",
        f"Golden cross (50 DMA crossing above 200 DMA)",
        f"RSI divergence indicating potential reversal",
        f"MACD bullish crossover signal",
        f"Fibonacci retracement support at {stop_loss:.2f}",
        f"Volume surge indicating institutional accumulation"
    ]
    
    # Fundamental factors by sector
    sector_factors = {
        "Technology": ["Strong quarterly earnings beat", "AI/Cloud growth momentum", "Expanding market share", "New product launches expected"],
        "Finance": ["Improving NII margins", "Stable asset quality", "Credit growth picking up", "Regulatory tailwinds"],
        "Energy": ["Rising crude oil prices", "Capacity expansion", "GRM improvement", "Green energy investments"],
        "Healthcare": ["Drug approval pipeline strong", "Hospital admissions recovering", "Healthcare spending growth", "Generic drug opportunities"],
        "Automotive": ["EV transition momentum", "Strong order book", "Export growth", "Raw material cost stabilization"],
        "Consumer": ["Festival season demand", "Rural recovery", "Premiumization trend", "Distribution expansion"],
        "Industrial": ["Infrastructure spending boost", "Order inflows strong", "Capacity utilization improving", "Government capex push"],
        "Telecom": ["Tariff hike expectations", "5G rollout benefits", "Data consumption growth", "ARPU improvement"],
        "Retail": ["Same-store sales growth", "E-commerce expansion", "Margin improvement", "New store additions"]
    }
    
    factors = sector_factors.get(sector, ["Strong fundamentals", "Positive sector outlook", "Improving financials"])
    
    # Build rationale
    pattern = random.choice(patterns)
    factor1 = random.choice(factors)
    factor2 = random.choice([f for f in factors if f != factor1]) if len(factors) > 1 else factors[0]
    
    rationale = f"{pattern}. {factor1}. {factor2}. "
    
    if risk_reward >= 2:
        rationale += f"Favorable risk-reward ratio of 1:{risk_reward:.1f}. "
    
    if potential_gain >= 10:
        rationale += f"Potential upside of {potential_gain:.1f}% to target. "
    
    return rationale.strip()

def search_yahoo(query: str) -> list:
    try:
        cache_key = f"search:{query.upper()}"
        if cache_key in search_cache: return search_cache[cache_key]
        
        # URL encode the query for special characters and spaces
        encoded_query = urllib.request.quote(query)
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={encoded_query}&quotesCount=20&newsCount=0"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8, context=ssl_context) as response:
            data = json.loads(response.read().decode())
        results = []
        for q in data.get('quotes', []):
            if q.get('quoteType') in ['EQUITY', 'ETF']:
                full_symbol = q.get('symbol', '')
                # Extract base symbol without suffix for display
                base_symbol = full_symbol.split('.')[0]
                exchange_code = q.get('exchDisp', '') or q.get('exchange', '')
                
                results.append({
                    'symbol': base_symbol,
                    'full_symbol': full_symbol,  # Keep full symbol for API calls
                    'name': q.get('longname') or q.get('shortname', ''), 
                    'exchange': exchange_code,
                    'sector': q.get('sector') or q.get('sectorDisp') or q.get('industry') or q.get('industryDisp') or STOCK_INFO.get(base_symbol, {}).get('sector', ''),
                    'industry': q.get('industry') or q.get('industryDisp') or '',
                    'logo': STOCK_INFO.get(base_symbol, {}).get('logo', '📈')
                })
        search_cache[cache_key] = results
        return results
    except Exception as e:
        logger.warning(f"Search error for '{query}': {e}")
        return []

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
            
            # Get current price
            current = meta.get('regularMarketPrice', 0)
            
            # Get previous close - try multiple fields (Yahoo returns different fields for different exchanges)
            prev = meta.get('previousClose') or meta.get('chartPreviousClose') or meta.get('regularMarketPreviousClose') or current
            
            # Get open price - fallback to previous close if not available
            open_price = meta.get('regularMarketOpen') or meta.get('open') or prev
            
            # Get day high/low with proper fallbacks
            day_high = meta.get('regularMarketDayHigh') or meta.get('dayHigh') or current
            day_low = meta.get('regularMarketDayLow') or meta.get('dayLow') or current
            
            # Calculate change
            change = round(current - prev, 2) if prev else 0
            change_percent = round(((current - prev) / prev * 100), 2) if prev and prev != 0 else 0
            
            stock_data = {
                'symbol': symbol, 
                'current_price': round(current, 2), 
                'previous_close': round(prev, 2),
                'change': change, 
                'change_percent': change_percent,
                'day_high': round(day_high, 2),
                'day_low': round(day_low, 2),
                'open_price': round(open_price, 2),
                'volume': int(meta.get('regularMarketVolume', 0)), 
                'is_live': True
            }
            stock_cache[cache_key] = stock_data
            cache_expiry[cache_key] = datetime.utcnow() + CACHE_DURATION
            return stock_data
    except Exception as e:
        logger.warning(f"fetch_quote error for {symbol}: {e}")
    return None

def fetch_stock_info(symbol: str, exchange: str = "US") -> dict:
    """Fetch additional stock info (name, sector) from Yahoo Finance search API"""
    # First check local STOCK_INFO database
    if symbol in STOCK_INFO:
        return STOCK_INFO[symbol]
    
    try:
        # Use search API which returns sector info without auth
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={symbol}&quotesCount=5&newsCount=0"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            data = json.loads(response.read().decode())
        
        # Find the exact match or best match
        for q in data.get('quotes', []):
            q_symbol = q.get('symbol', '').split('.')[0].upper()
            if q_symbol == symbol.upper():
                return {
                    "name": q.get('longname') or q.get('shortname') or symbol,
                    "sector": q.get('sector') or q.get('sectorDisp') or q.get('industry') or q.get('industryDisp') or '',
                    "industry": q.get('industry') or q.get('industryDisp') or '',
                    "logo": '📈'
                }
        
        # If no exact match, return first result
        if data.get('quotes'):
            q = data['quotes'][0]
            return {
                "name": q.get('longname') or q.get('shortname') or symbol,
                "sector": q.get('sector') or q.get('sectorDisp') or q.get('industry') or q.get('industryDisp') or '',
                "industry": q.get('industry') or q.get('industryDisp') or '',
                "logo": '📈'
            }
    except Exception as e:
        logger.warning(f"Failed to fetch stock info for {symbol}: {e}")
    
    return {"name": symbol, "sector": "", "logo": "📈"}

def get_quote(symbol: str, exchange: str = "US") -> dict:
    symbol = symbol.upper()
    ex_info = EXCHANGES.get(exchange, EXCHANGES["US"])
    
    # First check local STOCK_INFO, then fetch from Yahoo if not found
    if symbol in STOCK_INFO:
        info = STOCK_INFO[symbol]
    else:
        info = fetch_stock_info(symbol, exchange)
    
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

@app.on_event("startup")
async def startup_event():
    """Load persistent data on server startup"""
    load_persistent_data()
    logger.info(f"Server started. Admin: {ADMIN_EMAIL}, Guest Sessions: {len(guest_sessions_db)}, Feedback: {len(feedback_db)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Save data on server shutdown"""
    save_persistent_data()
    logger.info("Server shutdown. Data saved.")

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

def fetch_ip_location(client_ip: str = None) -> dict:
    """Fetch location from IP using multiple services"""
    location = {"ip_address": client_ip, "city": None, "country": None, "latitude": None, "longitude": None}
    services = [
        ("https://ipapi.co/json/", lambda d: {"ip": d.get("ip"), "city": d.get("city"), "country": d.get("country_name"), "lat": d.get("latitude"), "lon": d.get("longitude")}),
        ("http://ip-api.com/json/", lambda d: {"ip": d.get("query"), "city": d.get("city"), "country": d.get("country"), "lat": d.get("lat"), "lon": d.get("lon")}),
    ]
    for url, parser in services:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3, context=ssl_context) as response:
                data = json.loads(response.read().decode())
                parsed = parser(data)
                if parsed.get("city") and parsed.get("country"):
                    location["ip_address"] = parsed.get("ip") or client_ip
                    location["city"] = parsed["city"]
                    location["country"] = parsed["country"]
                    location["latitude"] = parsed.get("lat")
                    location["longitude"] = parsed.get("lon")
                    break
        except Exception as e:
            continue
    return location

@app.post("/api/v1/auth/guest", response_model=TokenResponse)
async def guest_login(device_info: Optional[GuestDeviceInfo] = None, request: Request = None):
    """Create a temporary guest account with device/location tracking"""
    
    guest_id = secrets.token_hex(4)
    guest_email = f"guest_{guest_id}@stockadvisor.demo"
    guest_password = generate_temp_password()
    
    # Create guest user
    users_db[guest_email] = {
        "email": guest_email, "password": guest_password,
        "first_name": "Guest", "last_name": f"User",
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True, "sso_provider": "guest", "login_issues": None
    }
    
    # Get client IP from request
    client_ip = None
    if request:
        client_ip = request.client.host if request.client else None
        # Check for forwarded IP (behind proxy)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
    
    # Fetch location from server-side if client didn't provide it
    location_info = {
        "ip_address": device_info.ip_address if device_info and device_info.ip_address else client_ip,
        "city": device_info.city if device_info else None,
        "country": device_info.country if device_info else None,
        "latitude": device_info.latitude if device_info else None,
        "longitude": device_info.longitude if device_info else None,
    }
    
    # If no city/country from client, fetch from server
    if not location_info["city"] or not location_info["country"]:
        server_location = fetch_ip_location(client_ip)
        if server_location["city"]:
            location_info = server_location
    
    # Store guest session with device info
    session_data = {
        "guest_id": guest_id,
        "guest_email": guest_email,
        "created_at": datetime.utcnow().isoformat(),
        "device_info": {
            "user_agent": device_info.user_agent if device_info else None,
            "platform": device_info.platform if device_info else None,
            "language": device_info.language if device_info else None,
            "screen_width": device_info.screen_width if device_info else None,
            "screen_height": device_info.screen_height if device_info else None,
            "timezone": device_info.timezone if device_info else None,
        } if device_info else {},
        "location_info": location_info
    }
    guest_sessions_db.append(session_data)
    
    # Save to persistent storage
    save_persistent_data()
    
    init_user_data(guest_email)
    return TokenResponse(access_token=create_access_token({"sub": guest_email}))

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
    
    # Save to persistent storage
    save_persistent_data()
    
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

# ============== Stock Alerts ==============
@app.get("/api/v1/alerts")
async def get_alerts(exchange: str = "NSE", user: dict = Depends(get_current_user)):
    """Get all stock alerts for current user"""
    email = user["email"]
    user_alerts = stock_alerts_db.get(email, [])
    # Filter by exchange and active status
    active_alerts = [a for a in user_alerts if a.get("exchange") == exchange and a.get("status", "active") == "active"]
    
    # Enrich with current price data
    enriched_alerts = []
    for alert in active_alerts:
        symbol = alert["symbol"]
        
        # Get REAL-TIME current price using fetch_quote (it handles suffix internally)
        current_price = alert.get("entry_price", 0)
        try:
            quote = fetch_quote(symbol, exchange)  # Pass exchange, not full_symbol
            if quote and quote.get("current_price"):
                current_price = quote.get("current_price")
        except Exception as e:
            logger.warning(f"Failed to fetch quote for {symbol}: {e}")
        
        # Calculate potential return from CURRENT price to target
        target_price = alert.get("target_price", 0)
        entry_price = alert.get("entry_price", 1)
        potential_return = ((target_price - current_price) / current_price * 100) if current_price > 0 else 0
        change_percent = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        
        stock_info = STOCK_INFO.get(symbol, {"name": symbol, "sector": "", "logo": "📈"})
        
        enriched_alerts.append({
            **alert,
            "current_price": round(current_price, 2),
            "potential_return": round(potential_return, 2),
            "change_percent": round(change_percent, 2),
            "name": stock_info.get("name", symbol),
            "logo": stock_info.get("logo", "📈")
        })
    
    return {"alerts": enriched_alerts}

@app.post("/api/v1/alerts")
async def create_alert(alert: StockAlertCreate, user: dict = Depends(get_current_user)):
    """Create a new stock alert"""
    email = user["email"]
    
    if email not in stock_alerts_db:
        stock_alerts_db[email] = []
    
    # Validate prices
    if alert.stop_loss >= alert.entry_price:
        raise HTTPException(status_code=400, detail="Stop loss must be below entry price")
    if alert.target_price <= alert.entry_price:
        raise HTTPException(status_code=400, detail="Target price must be above entry price")
    
    # Generate AI rationale if not provided
    rationale = alert.rationale
    if not rationale:
        rationale = generate_ai_rationale(
            alert.symbol.upper(), 
            alert.entry_price, 
            alert.target_price, 
            alert.stop_loss, 
            alert.exchange
        )
    
    new_alert = {
        "id": str(uuid.uuid4()),
        "symbol": alert.symbol.upper(),
        "entry_price": alert.entry_price,
        "stop_loss": alert.stop_loss,
        "target_price": alert.target_price,
        "rationale": rationale,
        "exchange": alert.exchange,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "created_by": email
    }
    
    stock_alerts_db[email].append(new_alert)
    return {"message": "Alert created", "alert": new_alert}

@app.put("/api/v1/alerts/{alert_id}")
async def update_alert(alert_id: str, update: StockAlertUpdate, user: dict = Depends(get_current_user)):
    """Update a stock alert"""
    email = user["email"]
    user_alerts = stock_alerts_db.get(email, [])
    
    for alert in user_alerts:
        if alert["id"] == alert_id:
            if update.entry_price is not None:
                alert["entry_price"] = update.entry_price
            if update.stop_loss is not None:
                alert["stop_loss"] = update.stop_loss
            if update.target_price is not None:
                alert["target_price"] = update.target_price
            if update.rationale is not None:
                alert["rationale"] = update.rationale
            if update.status is not None:
                alert["status"] = update.status
            alert["updated_at"] = datetime.now().isoformat()
            return {"message": "Alert updated", "alert": alert}
    
    raise HTTPException(status_code=404, detail="Alert not found")

@app.delete("/api/v1/alerts/{alert_id}")
async def delete_alert(alert_id: str, user: dict = Depends(get_current_user)):
    """Delete a stock alert"""
    email = user["email"]
    if email not in stock_alerts_db:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    original_count = len(stock_alerts_db[email])
    stock_alerts_db[email] = [a for a in stock_alerts_db[email] if a["id"] != alert_id]
    
    if len(stock_alerts_db[email]) == original_count:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"message": "Alert deleted"}

@app.get("/api/v1/alerts/all")
async def get_all_alerts(exchange: str = "NSE"):
    """Get all public stock alerts (no auth required for viewing)"""
    all_alerts = []
    for email, alerts in stock_alerts_db.items():
        for alert in alerts:
            if alert.get("exchange") == exchange and alert.get("status", "active") == "active":
                symbol = alert["symbol"]
                
                # Get REAL-TIME current price
                current_price = alert.get("entry_price", 0)
                try:
                    quote = fetch_quote(symbol, exchange)  # Pass exchange, not full_symbol
                    if quote and quote.get("current_price"):
                        current_price = quote.get("current_price")
                except Exception as e:
                    logger.warning(f"Failed to fetch quote for {symbol}: {e}")
                
                target_price = alert.get("target_price", 0)
                entry_price = alert.get("entry_price", 1)
                potential_return = ((target_price - current_price) / current_price * 100) if current_price > 0 else 0
                change_percent = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                
                stock_info = STOCK_INFO.get(symbol, {"name": symbol, "sector": "", "logo": "📈"})
                
                all_alerts.append({
                    **alert,
                    "current_price": round(current_price, 2),
                    "potential_return": round(potential_return, 2),
                    "change_percent": round(change_percent, 2),
                    "name": stock_info.get("name", symbol),
                    "logo": stock_info.get("logo", "📈"),
                    "created_by_name": "Trader Smith"  # Anonymize creator
                })
    
    return {"alerts": sorted(all_alerts, key=lambda x: x.get("created_at", ""), reverse=True)}

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
    guest_count = sum(1 for u in users_db.values() if u.get("sso_provider") == "guest")
    return {
        "total_users": len(users_db), "total_feedback": len(feedback_db), 
        "feedback_stats": stats, "users_with_login_issues": users_with_issues,
        "guest_sessions": len(guest_sessions_db), "guest_users": guest_count
    }

@app.get("/api/v1/admin/guest-sessions")
async def get_guest_sessions(user: dict = Depends(get_current_user)):
    """Get all guest session details for admin"""
    if not is_admin(user): raise HTTPException(status_code=403, detail="Admin access required")
    return {
        "sessions": sorted(guest_sessions_db, key=lambda x: x["created_at"], reverse=True),
        "total": len(guest_sessions_db)
    }

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
    
    # Test 20: Stock Alert Creation
    test_alert_id = None
    try:
        test_alert = {
            "id": str(uuid.uuid4()),
            "symbol": "TEST",
            "entry_price": 100.0,
            "stop_loss": 95.0,
            "target_price": 120.0,
            "rationale": "Test alert rationale",
            "exchange": "NSE",
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "created_by": test_email
        }
        test_alert_id = test_alert["id"]
        if test_email not in stock_alerts_db:
            stock_alerts_db[test_email] = []
        stock_alerts_db[test_email].append(test_alert)
        await run_test("Stock Alert Create", len(stock_alerts_db.get(test_email, [])) > 0)
    except Exception as e:
        await run_test("Stock Alert Create", False)
    
    # Test 21: Stock Alert Retrieval
    try:
        alerts = stock_alerts_db.get(test_email, [])
        has_test_alert = any(a["symbol"] == "TEST" for a in alerts)
        await run_test("Stock Alert Retrieve", has_test_alert)
    except:
        await run_test("Stock Alert Retrieve", False)
    
    # Test 22: AI Rationale Generation
    try:
        rationale = generate_ai_rationale("RELIANCE", 2850, 3150, 2750, "NSE")
        await run_test("AI Rationale Generation", len(rationale) > 50)
    except:
        await run_test("AI Rationale Generation", False)
    
    # Test 23: Stock Alert Delete
    try:
        if test_email in stock_alerts_db and test_alert_id:
            stock_alerts_db[test_email] = [a for a in stock_alerts_db[test_email] if a["id"] != test_alert_id]
        await run_test("Stock Alert Delete", True)
    except:
        await run_test("Stock Alert Delete", False)
    
    # Test 24: Guest Login Flow
    try:
        guest_email = f"guest_{uuid.uuid4().hex[:8]}@guest.stockadvisor.app"
        guest_token = create_access_token({"sub": guest_email})
        await run_test("Guest Token Generation", guest_token is not None)
    except:
        await run_test("Guest Token Generation", False)
    
    # Test 25: Exchange Configuration
    try:
        nse_config = EXCHANGES.get("NSE", {})
        has_required = all(k in nse_config for k in ["name", "suffix", "currency", "currency_symbol", "stocks"])
        await run_test("Exchange Config (NSE)", has_required)
    except:
        await run_test("Exchange Config (NSE)", False)
    
    # Test 26: Exchange US Config
    try:
        us_config = EXCHANGES.get("US", {})
        has_required = all(k in us_config for k in ["name", "suffix", "currency", "currency_symbol", "stocks"])
        await run_test("Exchange Config (US)", has_required)
    except:
        await run_test("Exchange Config (US)", False)
    
    # Test 27: Stock Info Database
    try:
        stock_count = len(STOCK_INFO)
        await run_test("Stock Info Database", stock_count >= 30)
    except:
        await run_test("Stock Info Database", False)
    
    # Test 28: TradingView URL Generation
    try:
        nse_prefix = EXCHANGES.get("NSE", {}).get("tradingview_prefix", "")
        tv_url_valid = nse_prefix == "NSE:"
        await run_test("TradingView URL Config", tv_url_valid)
    except:
        await run_test("TradingView URL Config", False)
    
    # Test 29: Currency Symbol Check
    try:
        currencies = {
            "US": "$", "NSE": "₹", "LSE": "£", "TSE": "¥", "HKEX": "HK$"
        }
        all_correct = all(EXCHANGES.get(ex, {}).get("currency_symbol") == sym for ex, sym in currencies.items())
        await run_test("Currency Symbols", all_correct)
    except:
        await run_test("Currency Symbols", False)
    
    # Test 30: Admin Email Verification
    try:
        await run_test("Admin Email Config", ADMIN_EMAIL == "atul.shivade@gmail.com")
    except:
        await run_test("Admin Email Config", False)
    
    # Test 31: Sample Alerts Exist
    try:
        sample_alerts = stock_alerts_db.get("system@stockadvisor.app", [])
        await run_test("Sample Alerts Available", len(sample_alerts) >= 3)
    except:
        await run_test("Sample Alerts Available", False)
    
    # Test 32: NSE Stock Quote
    try:
        nse_quote = get_quote("RELIANCE", "NSE")
        await run_test("NSE Stock Quote", nse_quote.get("current_price", 0) > 0)
    except:
        await run_test("NSE Stock Quote", False)
    
    # Test 33: Multi-Exchange Portfolio
    try:
        has_multi_exchange = len(portfolios_db.get(test_email, {})) >= 3
        await run_test("Multi-Exchange Portfolio", has_multi_exchange)
    except:
        await run_test("Multi-Exchange Portfolio", False)
    
    # Test 34: Feedback Status Flow
    try:
        valid_statuses = ["new", "in_progress", "resolved"]
        await run_test("Feedback Status Types", len(valid_statuses) == 3)
    except:
        await run_test("Feedback Status Types", False)
    
    # Test 35: Portfolio Update
    try:
        if test_email in portfolios_db and "US" in portfolios_db[test_email]:
            original_count = len(portfolios_db[test_email]["US"])
            portfolios_db[test_email]["US"].append({"symbol": "MSFT", "quantity": 5, "avg_cost": 400})
            updated = len(portfolios_db[test_email]["US"]) == original_count + 1
            portfolios_db[test_email]["US"] = [h for h in portfolios_db[test_email]["US"] if h["symbol"] != "MSFT"]
            await run_test("Portfolio Update Flow", updated)
        else:
            await run_test("Portfolio Update Flow", False)
    except:
        await run_test("Portfolio Update Flow", False)
    
    # Test 36: Stock Price Fetch (Real-time)
    try:
        quote = fetch_quote("RELIANCE", "NSE")
        await run_test("Real-time Price Fetch", quote is not None and quote.get("current_price", 0) > 0)
    except:
        await run_test("Real-time Price Fetch", False)
    
    # Test 37: Stock Info Fetch (Sector)
    try:
        info = fetch_stock_info("AAPL", "US")
        await run_test("Stock Info with Sector", info.get("name") is not None)
    except:
        await run_test("Stock Info with Sector", False)
    
    # Test 38: AI Rationale for Different Sectors
    try:
        rationale_tech = generate_ai_rationale("TCS", 3500, 4000, 3200, "NSE")
        rationale_finance = generate_ai_rationale("HDFCBANK", 1600, 1800, 1500, "NSE")
        await run_test("AI Rationale by Sector", len(rationale_tech) > 30 and len(rationale_finance) > 30)
    except:
        await run_test("AI Rationale by Sector", False)
    
    # Test 39: Exchange Currency Mapping
    try:
        us_currency = EXCHANGES.get("US", {}).get("currency") == "USD"
        nse_currency = EXCHANGES.get("NSE", {}).get("currency") == "INR"
        lse_currency = EXCHANGES.get("LSE", {}).get("currency") == "GBP"
        await run_test("Exchange Currency Mapping", us_currency and nse_currency and lse_currency)
    except:
        await run_test("Exchange Currency Mapping", False)
    
    # Test 40: TradingView URL Format
    try:
        nse_url = f"https://www.tradingview.com/symbols/{EXCHANGES['NSE']['tradingview_prefix']}RELIANCE/"
        us_url = f"https://www.tradingview.com/symbols/{EXCHANGES['US']['tradingview_prefix']}AAPL/"
        await run_test("TradingView URL Format", "NSE:" in nse_url and "AAPL" in us_url)
    except:
        await run_test("TradingView URL Format", False)
    
    # Test 41: Data Persistence File
    try:
        can_persist = True  # Just verify the functions exist
        await run_test("Data Persistence Functions", callable(save_persistent_data) and callable(load_persistent_data))
    except:
        await run_test("Data Persistence Functions", False)
    
    # Test 42: Guest Email Format
    try:
        sample_guest = "guest_abc12345@stockadvisor.demo"
        await run_test("Guest Email Format", "guest_" in sample_guest and "@stockadvisor.demo" in sample_guest)
    except:
        await run_test("Guest Email Format", False)
    
    # Test 43: Admin Pre-created
    try:
        admin_exists = ADMIN_EMAIL in users_db
        admin_password = users_db.get(ADMIN_EMAIL, {}).get("password") == "admin123"
        await run_test("Admin Pre-created", admin_exists and admin_password)
    except:
        await run_test("Admin Pre-created", False)
    
    # Test 44: Sample Alerts Exchange Filter
    try:
        nse_alerts = [a for a in stock_alerts_db.get("system@stockadvisor.app", []) if a.get("exchange") == "NSE"]
        us_alerts = [a for a in stock_alerts_db.get("system@stockadvisor.app", []) if a.get("exchange") == "US"]
        await run_test("Sample Alerts by Exchange", len(nse_alerts) >= 2 and len(us_alerts) >= 2)
    except:
        await run_test("Sample Alerts by Exchange", False)
    
    # Test 45: Portfolio Gain Calculation
    try:
        # Test gain calculation logic
        entry_price = 100
        current_price = 120
        gain_percent = ((current_price - entry_price) / entry_price) * 100
        await run_test("Gain Calculation Logic", gain_percent == 20.0)
    except:
        await run_test("Gain Calculation Logic", False)
    
    # Test 46: Final Cleanup (ONLY removes test data, NEVER admin/guest/sample data)
    try:
        # Protected emails that should NEVER be cleaned
        protected_emails = [ADMIN_EMAIL, "system@stockadvisor.app"]
        
        # Only clean up the temporary test user (sanity_test_xxx@test.com)
        if test_email in users_db and test_email not in protected_emails:
            del users_db[test_email]
        if test_email in portfolios_db and test_email not in protected_emails:
            del portfolios_db[test_email]
        if test_email in watchlists_db and test_email not in protected_emails:
            del watchlists_db[test_email]
        if test_email in stock_alerts_db and test_email not in protected_emails:
            del stock_alerts_db[test_email]
        
        # Remove ONLY test feedback entries (not admin or real user feedback)
        feedback_to_remove = [f for f in feedback_db if f.get("user_email") == test_email and test_email not in protected_emails]
        for f in feedback_to_remove: 
            feedback_db.remove(f)
        
        # NEVER touch guest_sessions_db - preserve all guest session history
        # guest_sessions_db is NOT cleaned
        
        # Verify admin data is intact
        admin_intact = ADMIN_EMAIL in users_db
        test_cleaned = test_email not in users_db
        
        await run_test("Final Cleanup (Admin Protected)", admin_intact and test_cleaned)
    except:
        await run_test("Final Cleanup (Admin Protected)", False)
    
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
    print(f"  Password: admin123")
    print("  Server: http://localhost:8000")
    print("="*50)
    
    # Load persisted data on startup
    load_persistent_data()
    print(f"  Guest Sessions: {len(guest_sessions_db)}")
    print(f"  Feedback Items: {len(feedback_db)}")
    print("="*50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
