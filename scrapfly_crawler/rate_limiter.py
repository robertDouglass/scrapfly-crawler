import asyncio
import os
from typing import Optional

class RateLimiter:
    def __init__(self, initial_concurrency=None):
        # Get values from environment variables or use defaults
        self.concurrency = initial_concurrency or int(os.getenv('INITIAL_CONCURRENCY', 1))
        self.last_retry_after = None
        self.consecutive_429s = 0
        self.min_concurrency = int(os.getenv('MIN_CONCURRENCY', 1))
        self.max_concurrency = int(os.getenv('MAX_CONCURRENCY', 1))
        self.base_delay = int(os.getenv('BASE_DELAY', 5))

    def update_concurrency(self, status_code: int, retry_after: Optional[str] = None):
        if status_code == 429:
            self.consecutive_429s += 1
            # Reduce concurrency on rate limits
            self.concurrency = max(self.min_concurrency, self.concurrency - 1)
            if retry_after:
                self.last_retry_after = float(retry_after)
        else:
            self.consecutive_429s = 0
            # Gradually increase concurrency on success
            if self.consecutive_429s == 0:
                self.concurrency = min(self.max_concurrency, self.concurrency + 1)

    async def wait_if_needed(self):
        if self.last_retry_after:
            await asyncio.sleep(self.last_retry_after)
            self.last_retry_after = None
