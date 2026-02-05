import hashlib
import time
from typing import Optional
import uuid

import redis


class BotState:
    OUTBOX_KEY = "bot:outbox_chat_id"
    USER_TO_BAN_KEY = "bot:ban:user:{}"
    BAN_TO_USER_KEY = "bot:ban:token:{}"
    #   user_token : <hashed user id>
    #   reason     : <text>
    #   intention  : <text>
    #   admin_id   : <telegram user id>
    #   timestamp  : <unix timestamp>

    def __init__(self, redis_client: redis.Redis):
        self._r = redis_client

    # --- Helpers ---

    def _hash_user_id(self, user_id: int) -> str:
        return hashlib.sha256(str(user_id).encode()).hexdigest()

    def _generate_ban_token(self) -> str:
        return uuid.uuid4().hex

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

    def is_user_banned(self, user_id: int) -> bool:
        user_token = self._hash_user_id(user_id)
        key = self.USER_TO_BAN_KEY.format(user_token)
        return self._r.exists(key) == 1

    def get_ban_token_by_user(self, user_id: int) -> Optional[str]:
        user_token = self._hash_user_id(user_id)
        key = self.USER_TO_BAN_KEY.format(user_token)
        return self._r.get(key)

    def get_ban_info_by_ban_token(self, ban_token: str) -> Optional[dict]:
        ban_key = self.BAN_TO_USER_KEY.format(ban_token)
        return self._r.hgetall(ban_key)

    def ban_user(
        self, user_id: int, reason: str, intention: str, admin_id: int
    ) -> tuple[str, str]:
        user_token = self._hash_user_id(user_id)

        existing = self.get_ban_token_by_user(user_id)
        if existing:
            return user_token, existing

        ban_token = self._generate_ban_token()

        user_key = self.USER_TO_BAN_KEY.format(user_token)
        ban_key = self.BAN_TO_USER_KEY.format(ban_token)

        pipe = self._r.pipeline()
        pipe.set(user_key, ban_token)
        pipe.hset(
            ban_key,
            mapping={
                "user_token": user_token,
                "reason": reason,
                "intention": intention,
                "admin_id": admin_id,
                "timestamp": time.time(),
            },
        )
        pipe.execute()

        return user_token, ban_token

    def unban_user(self, ban_token: str) -> bool:
        ban_key = self.BAN_TO_USER_KEY.format(ban_token)
        ban_metadata = self._r.hgetall(ban_key)

        if not ban_metadata:
            return False

        user_key = self.USER_TO_BAN_KEY.format(ban_metadata["user_token"])

        pipe = self._r.pipeline()
        pipe.delete(ban_key)
        pipe.delete(user_key)
        pipe.execute()

        return True
