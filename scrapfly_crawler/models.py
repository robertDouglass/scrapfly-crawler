import os
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime

class CrawlStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class LinkMetadata:
    url: str
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    crawled_at: Optional[datetime] = None
    error: Optional[str] = None
    proxy_country: Optional[str] = None
    render_js: Optional[bool] = None
    timing: Optional[Dict] = None
    scrape_params: Dict = None

    def __post_init__(self):
        if self.scrape_params is None:
            # Check if render_js is set in environment variables
            render_js_env = os.getenv('RENDER_JS')
            render_js = render_js_env.lower() == 'true' if render_js_env is not None else False
            
            self.scrape_params = {
                "render_js": render_js,  # Default is False unless overridden by env var
                "asp": True,
                "debug": True,
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"macOS"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1"
                }
            }
