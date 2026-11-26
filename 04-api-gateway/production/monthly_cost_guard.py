import redis
from datetime import datetime

r = redis.Redis(host="localhost", port=6379)

def check_budget(user_id: str, estimated_cost: float) -> bool:
    """
    Return True nếu còn budget, False nếu vượt.

    Logic:
    - Mỗi user có budget $10/tháng
    - Track spending trong Redis
    - Reset đầu tháng
    """
    # TODO: Implement
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"

    current = float(r.get(key) or 0)

    if current + estimated_cost > 10:
        return False

    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)

    return True
