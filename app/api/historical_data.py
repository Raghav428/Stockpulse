from fastapi import APIRouter, HTTPException, status
from datetime import date as Date
from typing import List, Dict
from app.core.cassandra import session

router = APIRouter(prefix = '/api/v1/historical_data')

@router.get("/stocks/{symbol}/history")
async def history(
    date: Date,
    symbol: str
) -> List[Dict]:
    """
    Fetch historical tick data from Cassandra for a specific symbol and date.
    """
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cassandra session not initialized"
        )

    # Note: date is converted to string for the CQL query as the schema uses 'text' for date
    data = session.execute(
        "SELECT * FROM tick_data WHERE symbol = %s AND date = %s",
        (symbol, str(date))
    )
    
    # Convert Cassandra row objects to dictionaries for JSON serialization
    results = [dict(row._asdict()) for row in data]
    
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"No historical data found for {symbol} on {date}"
        )
        
    return results
    