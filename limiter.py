from fastapi import Request
from slowapi import Limiter

# Define a custom key function that respects X-Forwarded-For header
def get_real_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Get the first IP which should be the client's real IP
        return forwarded_for.split(",")[0].strip()
    return request.client.host  # Fallback to direct client IP

# Create limiter instance with custom key function
limiter = Limiter(key_func=get_real_client_ip)
