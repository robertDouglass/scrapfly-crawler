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
    """Scrape a URL with exponential backoff retry logic and increased delays.
    Will not retry for binary content like images."""
    """Scrape a URL with exponential backoff retry logic and increased delays"""
    # Get values from environment variables or use defaults
    max_retries = max_retries or int(os.getenv('MAX_RETRIES', 3))
    base_delay = base_delay or int(os.getenv('BASE_DELAY', 10))
    last_error = None
    for attempt in range(max_retries):
        try:
            # Add delay between attempts, increasing with each retry
            if attempt > 0:
                delay = base_delay * (2 ** attempt) + random.uniform(1, 3)
                logger.debug(f"Waiting {delay:.2f}s before retry {attempt + 1}")
                await asyncio.sleep(delay)
                # Add extra random delay to avoid synchronized retries
                await asyncio.sleep(random.uniform(1, 3))

            result = await client.async_scrape(ScrapeConfig(
                url=url,
                **scrape_params
            ))
            # Check content type and status code
            content_type = result.response.headers.get('content-type', '').lower()
            is_binary = any(binary_type in content_type for binary_type in ['image/', 'video/', 'audio/', 'application/octet-stream'])
            
            # Don't retry for binary content, 404s, or other client errors (4xx)
            if is_binary or (400 <= result.response.status_code < 500):
                return result
                
            # Check if we need to retry based on status code
            if result.response.status_code == 429:
                retry_after = result.response.headers.get('retry-after')
                delay = float(retry_after) if retry_after else base_delay * (2 ** attempt)
                logger.warning(f"Rate limited on {url}. Waiting {delay:.2f}s before retry.")
                await asyncio.sleep(delay)
                continue
                
            return result
            return result
            
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed for {url}. Retrying in {delay:.2f}s. Error: {str(e)}")
            else:
                logger.error(f"All retries failed for {url}. Final error: {str(e)}")
                raise last_error

async def scrape_url(client: ScrapflyClient, url: str, tracker: LinkTracker, rate_limiter: RateLimiter) -> Optional[Dict]:
    """Scrape a single URL and return the result data"""
    logger.debug(f"Starting to scrape URL: {url}")
    try:
        await rate_limiter.wait_if_needed()
        
        # Get or create metadata for this URL
        metadata = tracker.links.get(url, LinkMetadata(url=url))
        
        # Scrape with the current scrape_params (render_js will be False by default)
        result = await scrape_with_retry(client, url, metadata.scrape_params)
        
        # Update rate limiter based on response
        rate_limiter.update_concurrency(
            result.response.status_code,
            result.response.headers.get('retry-after')
        )
        
        logger.debug(f"Got response with status code: {result.response.status_code}")
        
        # Update tracker with result
        tracker.update_from_result(result, url, metadata.scrape_params)

        # Check content type
        content_type = result.response.headers.get('content-type', '').lower()
        is_binary = any(binary_type in content_type for binary_type in ['image/', 'video/', 'audio/', 'application/octet-stream'])
        
        data = {
            "url": url,
            "html": result.content if not is_binary else None,
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

        # Only try to parse HTML and extract links for non-binary content
        if not is_binary:
            # Extract and process all links
            all_links = result.selector.css("a::attr(href)").getall()
            logger.debug(f"Found {len(all_links)} raw links on page {url}")
            
            # Filter and add new links to tracker
            filtered_links = filter_links(tracker.base_url, all_links)
            for link in filtered_links:
                if tracker.add_link(link):
                    logger.debug(f"Added new link to track: {link}")
        else:
            logger.debug(f"Skipping HTML parsing for binary content: {url}")
            
        logger.debug(f"Prepared data for storage: {data['url']}, status: {data['metadata']['status_code']}")
        return data
        
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {str(e)}")
        tracker.update_status(url, CrawlStatus.FAILED, str(e))
        return None
