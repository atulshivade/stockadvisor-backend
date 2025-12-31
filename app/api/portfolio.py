# portfolio.py
# StockAdvisor Backend - Portfolio Management API Routes
# Created by Digital COE Gen AI Team

from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.models.schemas import (
    User, Portfolio, PortfolioResponse, HoldingSchema, Transaction,
    TransactionType, StockExchange
)
from app.api.auth import get_current_user
from app.services.stock_data import StockDataService

router = APIRouter()


@router.get("/", response_model=PortfolioResponse)
async def get_portfolio(current_user: User = Depends(get_current_user)):
    """
    Get user's portfolio with current holdings and values.
    
    Returns:
    - Total portfolio value
    - Holdings with current prices
    - Day gain/loss
    - Total gain/loss
    """
    portfolio = await Portfolio.find_one(Portfolio.user_id == str(current_user.id))
    
    if not portfolio:
        # Create empty portfolio if doesn't exist
        portfolio = Portfolio(user_id=str(current_user.id))
        await portfolio.insert()
    
    # Update holdings with current prices
    updated_holdings = []
    total_value = 0
    total_cost = 0
    day_gain = 0
    
    for holding in portfolio.holdings:
        try:
            exchange = StockExchange(holding.get("exchange", "NYSE"))
            quote = await StockDataService.get_quote(holding["symbol"], exchange)
            
            if quote:
                current_price = quote.current_price
                prev_close = quote.previous_close
            else:
                current_price = holding.get("current_price", 0)
                prev_close = current_price
            
            quantity = holding["quantity"]
            avg_cost = holding["average_cost"]
            value = quantity * current_price
            cost = quantity * avg_cost
            gain = value - cost
            day_change = quantity * (current_price - prev_close)
            
            updated_holdings.append(HoldingSchema(
                stock_symbol=holding["symbol"],
                name=holding.get("name", holding["symbol"]),
                exchange=exchange,
                quantity=quantity,
                average_cost=avg_cost,
                current_price=current_price,
                total_value=value,
                gain=gain,
                gain_percent=(gain / cost * 100) if cost > 0 else 0
            ))
            
            total_value += value
            total_cost += cost
            day_gain += day_change
            
        except Exception as e:
            logger.warning(f"Error updating holding {holding.get('symbol')}: {e}")
    
    total_gain = total_value - total_cost
    
    return PortfolioResponse(
        id=str(portfolio.id),
        user_id=str(current_user.id),
        holdings=updated_holdings,
        total_value=round(total_value, 2),
        total_gain=round(total_gain, 2),
        total_gain_percent=round((total_gain / total_cost * 100) if total_cost > 0 else 0, 2),
        day_gain=round(day_gain, 2),
        day_gain_percent=round((day_gain / (total_value - day_gain) * 100) if (total_value - day_gain) > 0 else 0, 2),
        last_updated=datetime.utcnow()
    )


@router.post("/buy")
async def buy_stock(
    symbol: str,
    exchange: StockExchange,
    quantity: float,
    current_user: User = Depends(get_current_user)
):
    """
    Record a stock purchase.
    
    - **symbol**: Stock symbol
    - **exchange**: Stock exchange
    - **quantity**: Number of shares to buy
    """
    # Get current price
    quote = await StockDataService.get_quote(symbol.upper(), exchange)
    if not quote:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    
    price = quote.current_price
    total_amount = price * quantity
    
    # Get user's portfolio
    portfolio = await Portfolio.find_one(Portfolio.user_id == str(current_user.id))
    if not portfolio:
        portfolio = Portfolio(user_id=str(current_user.id))
    
    # Check if already holding this stock
    existing_holding = None
    holding_index = -1
    for i, h in enumerate(portfolio.holdings):
        if h.get("symbol") == symbol.upper() and h.get("exchange") == exchange.value:
            existing_holding = h
            holding_index = i
            break
    
    if existing_holding:
        # Update existing holding (average cost)
        old_qty = existing_holding["quantity"]
        old_cost = existing_holding["average_cost"]
        new_qty = old_qty + quantity
        new_avg_cost = ((old_qty * old_cost) + (quantity * price)) / new_qty
        
        portfolio.holdings[holding_index] = {
            "symbol": symbol.upper(),
            "name": quote.name,
            "exchange": exchange.value,
            "quantity": new_qty,
            "average_cost": new_avg_cost,
            "current_price": price
        }
    else:
        # Add new holding
        portfolio.holdings.append({
            "symbol": symbol.upper(),
            "name": quote.name,
            "exchange": exchange.value,
            "quantity": quantity,
            "average_cost": price,
            "current_price": price
        })
    
    portfolio.updated_at = datetime.utcnow()
    await portfolio.save()
    
    # Record transaction
    transaction = Transaction(
        user_id=str(current_user.id),
        stock_symbol=symbol.upper(),
        exchange=exchange,
        transaction_type=TransactionType.BUY,
        quantity=quantity,
        price=price,
        total_amount=total_amount
    )
    await transaction.insert()
    
    logger.info(f"User {current_user.id} bought {quantity} shares of {symbol}")
    
    return {
        "message": f"Successfully purchased {quantity} shares of {symbol}",
        "symbol": symbol.upper(),
        "quantity": quantity,
        "price": price,
        "total_amount": total_amount
    }


@router.post("/sell")
async def sell_stock(
    symbol: str,
    exchange: StockExchange,
    quantity: float,
    current_user: User = Depends(get_current_user)
):
    """
    Record a stock sale.
    
    - **symbol**: Stock symbol
    - **exchange**: Stock exchange
    - **quantity**: Number of shares to sell
    """
    # Get current price
    quote = await StockDataService.get_quote(symbol.upper(), exchange)
    if not quote:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    
    price = quote.current_price
    
    # Get user's portfolio
    portfolio = await Portfolio.find_one(Portfolio.user_id == str(current_user.id))
    if not portfolio:
        raise HTTPException(status_code=400, detail="No portfolio found")
    
    # Find holding
    holding_index = -1
    for i, h in enumerate(portfolio.holdings):
        if h.get("symbol") == symbol.upper() and h.get("exchange") == exchange.value:
            holding_index = i
            break
    
    if holding_index == -1:
        raise HTTPException(status_code=400, detail=f"You don't own any shares of {symbol}")
    
    holding = portfolio.holdings[holding_index]
    
    if holding["quantity"] < quantity:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient shares. You have {holding['quantity']} shares of {symbol}"
        )
    
    total_amount = price * quantity
    
    # Update or remove holding
    if holding["quantity"] == quantity:
        portfolio.holdings.pop(holding_index)
    else:
        portfolio.holdings[holding_index]["quantity"] -= quantity
        portfolio.holdings[holding_index]["current_price"] = price
    
    portfolio.updated_at = datetime.utcnow()
    await portfolio.save()
    
    # Record transaction
    transaction = Transaction(
        user_id=str(current_user.id),
        stock_symbol=symbol.upper(),
        exchange=exchange,
        transaction_type=TransactionType.SELL,
        quantity=quantity,
        price=price,
        total_amount=total_amount
    )
    await transaction.insert()
    
    logger.info(f"User {current_user.id} sold {quantity} shares of {symbol}")
    
    return {
        "message": f"Successfully sold {quantity} shares of {symbol}",
        "symbol": symbol.upper(),
        "quantity": quantity,
        "price": price,
        "total_amount": total_amount
    }


@router.get("/transactions", response_model=List[dict])
async def get_transactions(
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get user's transaction history."""
    transactions = await Transaction.find(
        Transaction.user_id == str(current_user.id)
    ).sort(-Transaction.timestamp).limit(limit).to_list()
    
    return [
        {
            "id": str(t.id),
            "symbol": t.stock_symbol,
            "exchange": t.exchange.value,
            "type": t.transaction_type.value,
            "quantity": t.quantity,
            "price": t.price,
            "total_amount": t.total_amount,
            "timestamp": t.timestamp.isoformat()
        }
        for t in transactions
    ]

