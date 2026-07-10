from app.cache.redis_client import redis_client

r = redis_client
async def get_next_port():
    port = await r.incr("deployment_per_counter")

    if port < 10000:
        await r.set("deployment_per_counter", 10000)
        return 10000

    return port