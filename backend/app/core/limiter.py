from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared Limiter instance to avoid circular imports between main and api
limiter = Limiter(key_func=get_remote_address)
