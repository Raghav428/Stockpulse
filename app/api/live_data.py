from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
import json
from app.core import redis as core_redis

router = APIRouter(prefix = '/api/v1/live_data')

@router.get("/stocks/{symbol}/live")
async def live(
    symbol: str
) -> Dict[str, Any]:
    """
    Fetch live tick data from Redis for a specific symbol.
    """

    data = await core_redis.redis_client.get(f"{symbol}")

    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"No live data found for {symbol}"
        )
    data = json.loads(data)

    return data
    