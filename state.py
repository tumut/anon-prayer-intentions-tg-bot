from typing import Optional

import redis


class BotState:
    OUTBOX_KEY = "bot:outbox_chat_id"
    BANNED_USERS_KEY = "bot:banned_users"

    def __init__(self, redis_client: redis.Redis):
        self._r = redis_client

    # --- Outbox chat ----

    def get_outbox_chat_id(self) -> Optional[int]:
        value = self._r.get(self.OUTBOX_KEY)
        if value is None:
            return None
        return int(value)

    def set_outbox_chat_id(self, chat_id: Optional[int]) -> None:
        if chat_id is None:
            self._r.delete(self.OUTBOX_KEY)
        else:
            self._r.set(self.OUTBOX_KEY, chat_id)

    # --- Banned users ---

    def is_user_banned(self, user_hash: str) -> bool:
        return self._r.sismember(self.BANNED_USERS_KEY, user_hash)

    def ban_user(self, user_hash: str) -> None:
        self._r.sadd(self.BANNED_USERS_KEY, user_hash)

    def unban_user(self, user_hash: str) -> None:
        self._r.srem(self.BANNED_USERS_KEY, user_hash)
