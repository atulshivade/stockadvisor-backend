# recommendation_engine.py
# StockAdvisor Backend - AI Recommendation Engine
# Created by Digital COE Gen AI Team

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import numpy as np
from loguru import logger

from app.models.schemas import (
    StockQuote, RecommendationResponse, RecommendationType,
    RiskTolerance, TimeHorizon, FundamentalMetrics, StockExchange,
    User, AISignal
)
from app.services.stock_data import StockDataService
from app.services.cache import CacheService
from app.config import settings


class AIRecommendationEngine:
    """
    AI-powered stock recommendation engine.
    Analyzes stocks based on fundamental metrics, technical indicators,
    and user's risk profile to generate personalized recommendations.
    """
    
    # Weights for different analysis factors
    FUNDAMENTAL_WEIGHT = 0.4
    TECHNICAL_WEIGHT = 0.3
    SENTIMENT_WEIGHT = 0.15
    RISK_ALIGNMENT_WEIGHT = 0.15
    
    # Fundamental metrics benchmarks
    PE_RATIO_BENCHMARKS = {
        "undervalued": 15,
        "fair": 25,
        "overvalued": 35
    }
    
    DEBT_EQUITY_BENCHMARKS = {
        "low": 0.5,
        "moderate": 1.0,
        "high": 2.0
    }
    
    ROE_BENCHMARKS = {
        "poor": 5,
        "fair": 15,
        "good": 25
    }
    
    @classmethod
    async def generate_recommendations(
        cls,
        user: User,
        symbols: Optional[List[str]] = None,
        exchanges: Optional[List[StockExchange]] = None,
        max_recommendations: int = 3
    ) -> List[RecommendationResponse]:
        """
        Generate AI-powered stock recommendations for a user.
        
        Args:
            user: User object with risk profile and preferences
            symbols: Optional list of specific symbols to analyze
            exchanges: Optional list of exchanges to consider
            max_recommendations: Maximum number of recommendations to return
            
        Returns:
            List of stock recommendations sorted by confidence score
        """
        logger.info(f"Generating recommendations for user {user.id}")
        
        # Use user's preferred exchanges if not specified
        if not exchanges:
            exchanges = user.preferred_exchanges
        
        # Get candidate stocks to analyze
        if not symbols:
            symbols = await cls._get_candidate_stocks(exchanges)
        
        recommendations = []
        
        for symbol in symbols:
            for exchange in exchanges:
                try:
                    recommendation = await cls._analyze_stock(
                        symbol=symbol,
                        exchange=exchange,
                        user_risk_tolerance=user.risk_tolerance,
                        user_investment_goal=user.investment_goal
                    )
                    
                    if recommendation and recommendation.confidence_score >= settings.RECOMMENDATION_CONFIDENCE_THRESHOLD:
                        recommendations.append(recommendation)
                        
                except Exception as e:
                    logger.warning(f"Error analyzing {symbol}: {e}")
                    continue
        
        # Sort by confidence score and return top recommendations
        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        return recommendations[:max_recommendations]
    
    @classmethod
    async def _get_candidate_stocks(
        cls, 
        exchanges: List[StockExchange]
    ) -> List[str]:
        """Get list of candidate stocks to analyze based on exchanges."""
        # Popular stocks by exchange (in production, this would come from a database)
        stock_universe = {
            StockExchange.NYSE: ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "JNJ", "V", "PG", "UNH", "HD"],
            StockExchange.NASDAQ: ["NVDA", "META", "TSLA", "NFLX", "ADBE", "INTC", "AMD", "PYPL", "CSCO", "CMCSA"],
            StockExchange.LSE: ["SHEL", "HSBA", "BP", "RIO", "GSK", "ULVR", "AZN", "BATS", "DGE", "LLOY"],
            StockExchange.TSE: ["7203", "6758", "9984", "6861", "8306", "9432", "4502", "6501", "7267", "6902"],
            StockExchange.HKEX: ["0700", "9988", "0005", "1299", "0941", "2318", "1398", "0883", "0388", "2628"],
            StockExchange.BSE: ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC", "BHARTIARTL", "KOTAKBANK", "LT"],
            StockExchange.NSE: ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC", "BHARTIARTL", "KOTAKBANK", "LT"],
        }
        
        candidates = []
        for exchange in exchanges:
            if exchange in stock_universe:
                candidates.extend(stock_universe[exchange])
        
        return list(set(candidates))  # Remove duplicates
    
    @classmethod
    async def _analyze_stock(
        cls,
        symbol: str,
        exchange: StockExchange,
        user_risk_tolerance: RiskTolerance,
        user_investment_goal: str
    ) -> Optional[RecommendationResponse]:
        """
        Perform comprehensive analysis on a single stock.
        
        Args:
            symbol: Stock symbol
            exchange: Stock exchange
            user_risk_tolerance: User's risk tolerance level
            user_investment_goal: User's investment goal
            
        Returns:
            RecommendationResponse or None if analysis fails
        """
        # Check cache first
        cache_key = f"recommendation:{symbol}:{exchange.value}:{user_risk_tolerance.value}"
        cached = await CacheService.get(cache_key)
        if cached:
            return RecommendationResponse(**cached)
        
        # Fetch stock data
        quote = await StockDataService.get_quote(symbol, exchange)
        if not quote:
            return None
        
        # Get fundamental metrics
        fundamental_metrics = await cls._get_fundamental_metrics(symbol, exchange)
        
        # Calculate scores
        fundamental_score = cls._calculate_fundamental_score(fundamental_metrics)
        technical_score = await cls._calculate_technical_score(symbol, exchange)
        sentiment_score = await cls._calculate_sentiment_score(symbol)
        risk_alignment_score = cls._calculate_risk_alignment(
            fundamental_metrics,
            user_risk_tolerance
        )
        
        # Calculate overall confidence score
        confidence_score = (
            fundamental_score * cls.FUNDAMENTAL_WEIGHT +
            technical_score * cls.TECHNICAL_WEIGHT +
            sentiment_score * cls.SENTIMENT_WEIGHT +
            risk_alignment_score * cls.RISK_ALIGNMENT_WEIGHT
        )
        
        # Determine recommendation type based on score
        recommendation_type = cls._get_recommendation_type(confidence_score)
        
        # Calculate target price
        target_price = cls._calculate_target_price(
            quote.current_price,
            confidence_score,
            recommendation_type
        )
        
        # Calculate potential return
        potential_return = ((target_price - quote.current_price) / quote.current_price) * 100
        
        # Generate rationale
        rationale = cls._generate_rationale(
            symbol,
            recommendation_type,
            fundamental_metrics,
            confidence_score
        )
        
        # Determine time horizon based on investment goal
        time_horizon = cls._get_time_horizon(user_investment_goal, recommendation_type)
        
        recommendation = RecommendationResponse(
            id=f"{symbol}_{exchange.value}_{datetime.utcnow().strftime('%Y%m%d')}",
            stock_symbol=symbol,
            stock_name=quote.name,
            exchange=exchange,
            recommendation_type=recommendation_type,
            confidence_score=round(confidence_score, 2),
            current_price=quote.current_price,
            target_price=round(target_price, 2),
            potential_return=round(potential_return, 2),
            rationale=rationale,
            risk_level=cls._assess_risk_level(fundamental_metrics),
            time_horizon=time_horizon,
            fundamental_metrics=FundamentalMetrics(**fundamental_metrics),
            created_at=datetime.utcnow()
        )
        
        # Cache the recommendation
        await CacheService.set(cache_key, recommendation.model_dump(), ttl=3600)
        
        return recommendation
    
    @classmethod
    async def _get_fundamental_metrics(
        cls, 
        symbol: str, 
        exchange: StockExchange
    ) -> Dict:
        """Get fundamental analysis metrics for a stock."""
        try:
            import yfinance as yf
            
            suffix = ""  # Add exchange suffix if needed
            ticker = yf.Ticker(f"{symbol}{suffix}")
            info = ticker.info
            
            return {
                "pe_ratio": info.get('trailingPE'),
                "pb_ratio": info.get('priceToBook'),
                "debt_to_equity": info.get('debtToEquity'),
                "roe": info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else None,
                "roa": info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else None,
                "current_ratio": info.get('currentRatio'),
                "revenue_growth": info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else None,
                "earnings_growth": info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') else None,
                "dividend_yield": info.get('dividendYield', 0) * 100 if info.get('dividendYield') else None,
                "price_to_sales": info.get('priceToSalesTrailing12Months')
            }
        except Exception as e:
            logger.warning(f"Error getting fundamentals for {symbol}: {e}")
            return {}
    
    @classmethod
    def _calculate_fundamental_score(cls, metrics: Dict) -> float:
        """Calculate fundamental analysis score (0-1)."""
        score = 0.5  # Base score
        factors = 0
        
        # P/E Ratio analysis
        pe_ratio = metrics.get('pe_ratio')
        if pe_ratio:
            if pe_ratio < cls.PE_RATIO_BENCHMARKS["undervalued"]:
                score += 0.15
            elif pe_ratio < cls.PE_RATIO_BENCHMARKS["fair"]:
                score += 0.10
            elif pe_ratio > cls.PE_RATIO_BENCHMARKS["overvalued"]:
                score -= 0.10
            factors += 1
        
        # Debt/Equity analysis
        de_ratio = metrics.get('debt_to_equity')
        if de_ratio:
            de_value = de_ratio / 100 if de_ratio > 10 else de_ratio
            if de_value < cls.DEBT_EQUITY_BENCHMARKS["low"]:
                score += 0.10
            elif de_value > cls.DEBT_EQUITY_BENCHMARKS["high"]:
                score -= 0.10
            factors += 1
        
        # ROE analysis
        roe = metrics.get('roe')
        if roe:
            if roe > cls.ROE_BENCHMARKS["good"]:
                score += 0.15
            elif roe > cls.ROE_BENCHMARKS["fair"]:
                score += 0.10
            elif roe < cls.ROE_BENCHMARKS["poor"]:
                score -= 0.10
            factors += 1
        
        # Revenue growth
        rev_growth = metrics.get('revenue_growth')
        if rev_growth:
            if rev_growth > 20:
                score += 0.10
            elif rev_growth > 10:
                score += 0.05
            elif rev_growth < 0:
                score -= 0.10
            factors += 1
        
        # Earnings growth
        earnings_growth = metrics.get('earnings_growth')
        if earnings_growth:
            if earnings_growth > 25:
                score += 0.10
            elif earnings_growth > 10:
                score += 0.05
            elif earnings_growth < 0:
                score -= 0.10
            factors += 1
        
        return max(0, min(1, score))
    
    @classmethod
    async def _calculate_technical_score(
        cls, 
        symbol: str, 
        exchange: StockExchange
    ) -> float:
        """Calculate technical analysis score (0-1)."""
        try:
            # Get price history
            history = await StockDataService.get_price_history(symbol, exchange, "3mo")
            
            if len(history) < 20:
                return 0.5
            
            prices = [h['close'] for h in history]
            
            # Calculate moving averages
            ma_20 = np.mean(prices[-20:])
            ma_50 = np.mean(prices[-50:]) if len(prices) >= 50 else ma_20
            current_price = prices[-1]
            
            score = 0.5
            
            # Price above MA20 (bullish)
            if current_price > ma_20:
                score += 0.15
            else:
                score -= 0.10
            
            # MA20 above MA50 (bullish trend)
            if ma_20 > ma_50:
                score += 0.10
            else:
                score -= 0.05
            
            # Price momentum (last 10 days)
            if len(prices) >= 10:
                momentum = (prices[-1] - prices[-10]) / prices[-10]
                if momentum > 0.05:
                    score += 0.15
                elif momentum > 0:
                    score += 0.05
                elif momentum < -0.05:
                    score -= 0.15
            
            # Volatility (lower is better for most investors)
            volatility = np.std(prices[-20:]) / np.mean(prices[-20:])
            if volatility < 0.02:
                score += 0.10
            elif volatility > 0.05:
                score -= 0.10
            
            return max(0, min(1, score))
            
        except Exception as e:
            logger.warning(f"Technical analysis error for {symbol}: {e}")
            return 0.5
    
    @classmethod
    async def _calculate_sentiment_score(cls, symbol: str) -> float:
        """Calculate market sentiment score (0-1)."""
        # In production, this would analyze news, social media, analyst ratings
        # For now, return a neutral score
        return 0.5
    
    @classmethod
    def _calculate_risk_alignment(
        cls, 
        metrics: Dict, 
        risk_tolerance: RiskTolerance
    ) -> float:
        """Calculate how well the stock aligns with user's risk tolerance."""
        stock_risk = cls._assess_risk_level(metrics)
        
        alignment_matrix = {
            (RiskTolerance.CONSERVATIVE, RiskTolerance.CONSERVATIVE): 1.0,
            (RiskTolerance.CONSERVATIVE, RiskTolerance.MODERATE): 0.7,
            (RiskTolerance.CONSERVATIVE, RiskTolerance.AGGRESSIVE): 0.3,
            (RiskTolerance.MODERATE, RiskTolerance.CONSERVATIVE): 0.7,
            (RiskTolerance.MODERATE, RiskTolerance.MODERATE): 1.0,
            (RiskTolerance.MODERATE, RiskTolerance.AGGRESSIVE): 0.7,
            (RiskTolerance.AGGRESSIVE, RiskTolerance.CONSERVATIVE): 0.3,
            (RiskTolerance.AGGRESSIVE, RiskTolerance.MODERATE): 0.7,
            (RiskTolerance.AGGRESSIVE, RiskTolerance.AGGRESSIVE): 1.0,
        }
        
        return alignment_matrix.get((risk_tolerance, stock_risk), 0.5)
    
    @classmethod
    def _assess_risk_level(cls, metrics: Dict) -> RiskTolerance:
        """Assess the risk level of a stock based on its metrics."""
        risk_score = 0
        
        # High debt increases risk
        de_ratio = metrics.get('debt_to_equity', 0)
        if de_ratio:
            de_value = de_ratio / 100 if de_ratio > 10 else de_ratio
            if de_value > 2:
                risk_score += 2
            elif de_value > 1:
                risk_score += 1
        
        # High P/E can indicate higher risk
        pe_ratio = metrics.get('pe_ratio', 0)
        if pe_ratio:
            if pe_ratio > 40:
                risk_score += 2
            elif pe_ratio > 25:
                risk_score += 1
        
        # Negative earnings growth increases risk
        earnings_growth = metrics.get('earnings_growth')
        if earnings_growth and earnings_growth < 0:
            risk_score += 1
        
        if risk_score >= 3:
            return RiskTolerance.AGGRESSIVE
        elif risk_score >= 1:
            return RiskTolerance.MODERATE
        else:
            return RiskTolerance.CONSERVATIVE
    
    @classmethod
    def _get_recommendation_type(cls, confidence_score: float) -> RecommendationType:
        """Determine recommendation type based on confidence score."""
        if confidence_score >= 0.85:
            return RecommendationType.STRONG_BUY
        elif confidence_score >= 0.70:
            return RecommendationType.BUY
        elif confidence_score >= 0.45:
            return RecommendationType.HOLD
        elif confidence_score >= 0.30:
            return RecommendationType.SELL
        else:
            return RecommendationType.STRONG_SELL
    
    @classmethod
    def _calculate_target_price(
        cls, 
        current_price: float, 
        confidence_score: float,
        recommendation_type: RecommendationType
    ) -> float:
        """Calculate target price based on analysis."""
        multipliers = {
            RecommendationType.STRONG_BUY: 1.15 + (confidence_score - 0.85) * 0.5,
            RecommendationType.BUY: 1.10 + (confidence_score - 0.70) * 0.33,
            RecommendationType.HOLD: 1.0 + (confidence_score - 0.45) * 0.2,
            RecommendationType.SELL: 0.95 - (0.45 - confidence_score) * 0.33,
            RecommendationType.STRONG_SELL: 0.85 - (0.30 - confidence_score) * 0.5,
        }
        
        multiplier = multipliers.get(recommendation_type, 1.0)
        return current_price * max(0.5, min(2.0, multiplier))
    
    @classmethod
    def _generate_rationale(
        cls,
        symbol: str,
        recommendation_type: RecommendationType,
        metrics: Dict,
        confidence_score: float
    ) -> str:
        """Generate human-readable rationale for the recommendation."""
        reasons = []
        
        pe_ratio = metrics.get('pe_ratio')
        if pe_ratio:
            if pe_ratio < 15:
                reasons.append("attractively valued with low P/E ratio")
            elif pe_ratio > 35:
                reasons.append("premium valuation may limit upside")
        
        roe = metrics.get('roe')
        if roe:
            if roe > 25:
                reasons.append("strong return on equity indicates efficient management")
            elif roe < 5:
                reasons.append("low ROE suggests operational challenges")
        
        rev_growth = metrics.get('revenue_growth')
        if rev_growth:
            if rev_growth > 20:
                reasons.append("impressive revenue growth trajectory")
            elif rev_growth < 0:
                reasons.append("declining revenue is a concern")
        
        de_ratio = metrics.get('debt_to_equity')
        if de_ratio:
            de_value = de_ratio / 100 if de_ratio > 10 else de_ratio
            if de_value < 0.5:
                reasons.append("healthy balance sheet with low debt")
            elif de_value > 2:
                reasons.append("high debt levels increase risk")
        
        if not reasons:
            reasons.append("balanced fundamentals align with market expectations")
        
        action = {
            RecommendationType.STRONG_BUY: "Strongly recommend buying",
            RecommendationType.BUY: "Recommend buying",
            RecommendationType.HOLD: "Recommend holding",
            RecommendationType.SELL: "Recommend selling",
            RecommendationType.STRONG_SELL: "Strongly recommend selling",
        }
        
        return f"{action[recommendation_type]} {symbol}. Analysis shows {', '.join(reasons)}."
    
    @classmethod
    def _get_time_horizon(
        cls, 
        investment_goal: str, 
        recommendation_type: RecommendationType
    ) -> TimeHorizon:
        """Determine appropriate time horizon for the recommendation."""
        if investment_goal == "speculation":
            return TimeHorizon.SHORT_TERM
        elif investment_goal == "growth":
            return TimeHorizon.LONG_TERM
        elif recommendation_type in [RecommendationType.STRONG_BUY, RecommendationType.BUY]:
            return TimeHorizon.MEDIUM_TERM
        else:
            return TimeHorizon.SHORT_TERM

