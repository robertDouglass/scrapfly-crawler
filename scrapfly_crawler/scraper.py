import logging
import asyncio
import random
import os
from typing import Dict, Optional
from scrapfly import ScrapflyClient, ScrapeConfig
from .tracker import LinkTracker
from .rate_limiter import RateLimiter
from .utils import filter_links
from .models import LinkMetadata, CrawlStatus

logger = logging.getLogger(__name__)

async def scrape_with_retry(client: ScrapflyClient, url: str, scrape_params: Dict, max_retries=None, base_delay=None):
    """Scrape a URL with retry logic for network and server errors only."""
    max_retries = max_retries or int(os.getenv('MAX_RETRIES', 3))
    base_delay = base_delay or int(os.getenv('BASE_DELAY', 10))
    last_error = None

    for attempt in range(max_retries):
        try:
            # Add delay between attempts
            if attempt > 0:
                delay = base_delay * (2 ** attempt) + random.uniform(1, 3)
                logger.debug(f"Waiting {delay:.2f}s before retry {attempt + 1}")
                await asyncio.sleep(delay)

            result = await client.async_scrape(ScrapeConfig(
                url=url,
                **scrape_params
            ))

            # Check if response indicates a server error (5xx)
            if 500 <= result.response.status_code < 600:
                if attempt < max_retries - 1:
                    logger.warning(f"Server error {result.response.status_code} for {url}. Will retry.")
                    continue
                logger.error(f"Server error {result.response.status_code} persisted after all retries for {url}")
                return result

            # For rate limits, respect retry-after header
            if result.response.status_code == 429:
                if attempt < max_retries - 1:
                    retry_after = result.response.headers.get('retry-after')
                    delay = float(retry_after) if retry_after else base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited on {url}. Waiting {delay:.2f}s before retry.")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"Rate limiting persisted after all retries for {url}")
                return result

            # All other responses (including 4xx) are returned without retry
            return result

        except (asyncio.TimeoutError, ConnectionError) as e:
            # Only retry network-related errors
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(f"Network error on attempt {attempt + 1} for {url}: {str(e)}. Will retry.")
                continue
            logger.error(f"Network error persisted after all retries for {url}: {str(e)}")
            raise last_error
        except Exception as e:
            # Don't retry other exceptions
            logger.error(f"Non-retryable error for {url}: {str(e)}")
            raise e

async def scrape_url(client: ScrapflyClient, url: str, tracker: LinkTracker, rate_limiter: RateLimiter) -> Optional[Dict]:
    """Scrape a single URL and return the result data"""
    logger.debug(f"Starting to scrape URL: {url}")
    
    # Skip binary content URLs
    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3', '.pdf', '.zip']):
        logger.debug(f"Skipping binary content URL: {url}")
        return None
        
    try:
        await rate_limiter.wait_if_needed()
        metadata = tracker.links.get(url, LinkMetadata(url=url))
        
        # Scrape with retry only for network/server errors
        result = await scrape_with_retry(client, url, metadata.scrape_params)
        
        # Update rate limiter based on response
        rate_limiter.update_concurrency(
            result.response.status_code,
            result.response.headers.get('retry-after')
        )
        
        # Check for client errors (4xx)
        if 400 <= result.response.status_code < 500:
            logger.debug(f"Client error {result.response.status_code} for {url}")
            tracker.update_status(url, CrawlStatus.FAILED, f"Client error: {result.response.status_code}")
            return None
            
        # Check content type
        content_type = result.response.headers.get('content-type', '').lower()
        is_binary = any(binary_type in content_type for binary_type in ['image/', 'video/', 'audio/', 'application/octet-stream'])
        
        if is_binary:
            logger.debug(f"Skipping binary content response: {url}")
            return None
            
        # Update tracker with result
        tracker.update_from_result(result, url, metadata.scrape_params)
        
        data = {
            "url": url,
            "html": result.content,
            "metadata": {
                "status_code": metadata.status_code,
                "content_type": metadata.content_type,
                "crawled_at": metadata.crawled_at.isoformat(),
                "proxy_country": metadata.proxy_country,
                "render_js": metadata.render_js,
                "timing": metadata.timing,
                "scrape_params": metadata.scrape_params
            }
        }

        # Extract and process links
        all_links = result.selector.css("a::attr(href)").getall()
        logger.debug(f"Found {len(all_links)} raw links on page {url}")
        
        # Filter and add new links to tracker
        filtered_links = filter_links(tracker.base_url, all_links)
        for link in filtered_links:
            if tracker.add_link(link):
                logger.debug(f"Added new link to track: {link}")
                
        logger.debug(f"Prepared data for storage: {data['url']}, status: {data['metadata']['status_code']}")
        return data
        
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {str(e)}")
        tracker.update_status(url, CrawlStatus.FAILED, str(e))
        return None
