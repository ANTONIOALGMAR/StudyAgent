from fastapi import Request


def _normalize_user_candidate(candidate: str | None) -> str:
    if not candidate:
        return "default"
    c = candidate.strip()
    if not c:
        return "default"
    return c.lower().replace(" ", "_")


async def get_current_user(request: Request) -> str:
    """FastAPI dependency: determine the acting user.

    Priority:
    1. X-User-Id header
    2. X-User header
    3. session_id cookie
    4. default -> 'default'

    Returns a normalized user id string (lowercase, spaces -> underscore).
    """
    header = request.headers.get("X-User-Id") or request.headers.get("X-User")
    if header and header.strip():
        return _normalize_user_candidate(header)
    cookie = request.cookies.get("session_id")
    if cookie and cookie.strip():
        return _normalize_user_candidate(cookie)
    # fallback to client IP as weak identifier (not recommended for production)
    client = None
    try:
        client = request.client.host if request.client else None
    except Exception:
        client = None
    if client:
        return _normalize_user_candidate(client)
    return "default"
