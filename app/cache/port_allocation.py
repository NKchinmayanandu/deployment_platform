from app.cache.redis_client import redis_client
import subprocess

r = redis_client

def get_next_port():
    port = r.incr("deployment_per_counter")
    if port<8000:
        r.set("deployment_per_counter",8000)
        return 8000
    return port
