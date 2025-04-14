"""
Scrapfly Crawler - A web crawler using the Scrapfly API

This package provides a robust web crawler implementation using the Scrapfly API
for handling JavaScript rendering, proxy rotation, and rate limiting.
"""

from .crawler import Crawler
from .models import CrawlStatus, LinkMetadata
from .tracker import LinkTracker
from .rate_limiter import RateLimiter

__version__ = "0.1.0"
__all__ = ['Crawler', 'CrawlStatus', 'LinkMetadata', 'LinkTracker', 'RateLimiter']