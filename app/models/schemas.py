# schemas.py
# StockAdvisor Backend - Pydantic Schemas & MongoDB Models
# Created by Digital COE Gen AI Team

from datetime import datetime
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, EmailStr
from beanie import Document, Indexed


# MARK: - Enums
class RiskTolerance(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class InvestmentGoal(str, Enum):
    GROWTH = "growth"
    INCOME = "income"
    PRESERVATION = "preservation"
    SPECULATION = "speculation"


class StockExchange(str, Enum):
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    LSE = "LSE"
    TSE = "TSE"
    HKEX = "HKEX"
    SSE = "SSE"
    BSE = "BSE"
    NSE = "NSE"
    ASX = "ASX"
    TSX = "TSX"
    FRA = "FRA"
    SIX = "SIX"


class RecommendationType(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class TimeHorizon(str, Enum):
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class TransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"


class InsightCategory(str, Enum):
    MARKET_TREND = "market_trend"
    SECTOR_ANALYSIS = "sector_analysis"
    EARNINGS_REPORT = "earnings_report"
    ECONOMIC_NEWS = "economic_news"
    AI_PREDICTION = "ai_prediction"


class ImpactLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# MARK: - MongoDB Documents

class User(Document):
    """User document for MongoDB."""
    email: Indexed(str, unique=True)
    hashed_password: str
    first_name: str
    last_name: str
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    investment_goal: InvestmentGoal = InvestmentGoal.GROWTH
    preferred_exchanges: List[StockExchange] = [StockExchange.NYSE, StockExchange.NASDAQ]
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    login_attempts: int = 0
    locked_until: Optional[datetime] = None
    
    class Settings:
        name = "users"


class Portfolio(Document):
    """Portfolio document for MongoDB."""
    user_id: Indexed(str)
    holdings: List[dict] = []
    total_value: float = 0.0
    total_cost: float = 0.0
    total_gain: float = 0.0
    total_gain_percent: float = 0.0
    day_gain: float = 0.0
    day_gain_percent: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "portfolios"


class Watchlist(Document):
    """Watchlist document for MongoDB."""
    user_id: Indexed(str)
    name: str = "My Watchlist"
    symbols: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "watchlists"


class Transaction(Document):
    """Transaction document for MongoDB."""
    user_id: Indexed(str)
    stock_symbol: str
    exchange: StockExchange
    transaction_type: TransactionType
    quantity: float
    price: float
    total_amount: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "transactions"


class AISignal(Document):
    """AI Signal/Recommendation document for MongoDB."""
    stock_symbol: Indexed(str)
    exchange: StockExchange
    recommendation_type: RecommendationType
    confidence_score: float
    target_price: float
    current_price: float
    potential_return: float
    rationale: str
    risk_level: RiskTolerance
    time_horizon: TimeHorizon
    fundamental_metrics: dict
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    is_active: bool = True
    
    class Settings:
        name = "ai_signals"


class MarketInsight(Document):
    """Market Insight document for MongoDB."""
    title: str
    summary: str
    content: Optional[str] = None
    category: InsightCategory
    impact: ImpactLevel
    related_stocks: List[str] = []
    source: Optional[str] = None
    published_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "market_insights"


# MARK: - API Request/Response Schemas

class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    investment_goal: InvestmentGoal = InvestmentGoal.GROWTH
    preferred_exchanges: List[StockExchange] = [StockExchange.NYSE, StockExchange.NASDAQ]


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response (excluding sensitive data)."""
    id: str
    email: str
    first_name: str
    last_name: str
    risk_tolerance: RiskTolerance
    investment_goal: InvestmentGoal
    preferred_exchanges: List[StockExchange]
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for user profile update."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    risk_tolerance: Optional[RiskTolerance] = None
    investment_goal: Optional[InvestmentGoal] = None
    preferred_exchanges: Optional[List[StockExchange]] = None


class TokenResponse(BaseModel):
    """Schema for authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    """Schema for authentication response."""
    token: TokenResponse
    user: UserResponse


class StockQuote(BaseModel):
    """Schema for real-time stock quote."""
    symbol: str
    name: str
    exchange: StockExchange
    current_price: float
    previous_close: float
    change: float
    change_percent: float
    day_high: float
    day_low: float
    volume: int
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    week_52_high: float
    week_52_low: float
    last_updated: datetime


class StockSearch(BaseModel):
    """Schema for stock search results."""
    symbol: str
    name: str
    exchange: StockExchange
    type: str = "stock"


class HoldingSchema(BaseModel):
    """Schema for portfolio holding."""
    stock_symbol: str
    name: str
    exchange: StockExchange
    quantity: float
    average_cost: float
    current_price: float
    total_value: float
    gain: float
    gain_percent: float


class PortfolioResponse(BaseModel):
    """Schema for portfolio response."""
    id: str
    user_id: str
    holdings: List[HoldingSchema]
    total_value: float
    total_gain: float
    total_gain_percent: float
    day_gain: float
    day_gain_percent: float
    last_updated: datetime


class FundamentalMetrics(BaseModel):
    """Schema for fundamental analysis metrics."""
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    current_ratio: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    dividend_yield: Optional[float] = None
    price_to_sales: Optional[float] = None


class RecommendationResponse(BaseModel):
    """Schema for AI recommendation response."""
    id: str
    stock_symbol: str
    stock_name: str
    exchange: StockExchange
    recommendation_type: RecommendationType
    confidence_score: float
    current_price: float
    target_price: float
    potential_return: float
    rationale: str
    risk_level: RiskTolerance
    time_horizon: TimeHorizon
    fundamental_metrics: FundamentalMetrics
    created_at: datetime


class WatchlistResponse(BaseModel):
    """Schema for watchlist response."""
    id: str
    name: str
    stocks: List[StockQuote]
    created_at: datetime
    updated_at: datetime


class MarketInsightResponse(BaseModel):
    """Schema for market insight response."""
    id: str
    title: str
    summary: str
    category: InsightCategory
    impact: ImpactLevel
    related_stocks: List[str]
    published_at: datetime


class PriceUpdate(BaseModel):
    """Schema for WebSocket price update."""
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: int
    timestamp: datetime


class APIResponse(BaseModel):
    """Generic API response wrapper."""
    success: bool
    data: Optional[dict] = None
    message: Optional[str] = None
    error: Optional[str] = None

