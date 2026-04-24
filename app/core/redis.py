import redis.asyncio as aioredis

redis_client = None

async def connect_redis():
    global redis_client
    redis_client = aioredis.Redis(host='my_redis', port=6379)
    if redis_client:
        return redis_client
    return None

async def close_redis():
    await redis_client.aclose()