import json
import redis
from typing import List, Dict, Optional
from app.core.config import get_settings

settings = get_settings()

# Initialize Global Redis Client for History
# Uses the same Redis instance as Celery for efficiency.
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

class HistoryManager:
    """
    Elite Redis History Manager.
    Handles 'Short-term Context' (Dialogue flow) and 'Entity Facts' (User name).
    """
    
    @staticmethod
    def get_history_key(session_id: str) -> str:
        return f"chat_history:{session_id}"

    @staticmethod
    def get_profile_key(session_id: str) -> str:
        return f"user_profile:{session_id}"

    @classmethod
    def add_message(cls, session_id: str, role: str, content: str):
        """Adds a message to the sliding window (List) in Redis."""
        key = cls.get_history_key(session_id)
        message = json.dumps({"role": role, "content": content})
        
        # 1. Store in List
        redis_client.rpush(key, message)
        
        # 2. Enforce Sliding Window (Keep only last 10 messages)
        redis_client.ltrim(key, -10, -1)
        
        # 3. Set expiration (24 hours activity)
        redis_client.expire(key, 86400)

    @classmethod
    def get_history(cls, session_id: str) -> List[Dict[str, str]]:
        """Retrieves history as a list of dictionaries."""
        key = cls.get_history_key(session_id)
        raw_history = redis_client.lrange(key, 0, -1)
        return [json.loads(m) for m in raw_history]

    @classmethod
    def get_history_as_string(cls, session_id: str) -> str:
        """Formats the history for prompt injection."""
        history = cls.get_history(session_id)
        formatted = []
        for msg in history:
            role = "Human" if msg["role"] == "user" else "Assistant"
            formatted.append(f"{role}: {msg['content']}")
        return "\n".join(formatted)

    @classmethod
    def store_fact(cls, session_id: str, key: str, value: str):
        """Stores a persistent session fact (like user name)."""
        profile_key = cls.get_profile_key(session_id)
        redis_client.hset(profile_key, key, value)
        redis_client.expire(profile_key, 86400 * 7) # Profiles last 1 week

    @classmethod
    def get_profile(cls, session_id: str) -> Dict[str, str]:
        """Gets all stored facts about the user for this session."""
        profile_key = cls.get_profile_key(session_id)
        return redis_client.hgetall(profile_key) or {}

    @classmethod
    def clear_session(cls, session_id: str):
        """Wipes memory for a fresh start."""
        redis_client.delete(cls.get_history_key(session_id))
        redis_client.delete(cls.get_profile_key(session_id))
