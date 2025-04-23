import logging
import asyncio
import random
import os
from typing import Dict, Optional
from scrapfly import ScrapflyClient, ScrapeConfig
from .tracker import LinkTracker
from .rate_limiter import RateLimiter
from .utils import filter_links, should_exclude_url
from .models import LinkMetadata, CrawlStatus

logger = logging.getLogger(__name__)

async def scrape_with_retry(client: ScrapflyClient, url: str, scrape_params: Dict, max_retries=None, base_delay=None):
    """Scrape a URL with retry logic for network and server errors only."""
    max_retries = max_retries or int(os.getenv('MAX_RETRIES', 3))
    base_delay = base_delay or int(os.getenv('BASE_DELAY', 10))
    timeout = int(os.getenv('SCRAPE_TIMEOUT', 30))  # Default 30 seconds timeout
    last_error = None

    for attempt in range(max_retries):
        try:
            # Add delay between attempts
            if attempt > 0:
                delay = base_delay * (2 ** attempt) + random.uniform(1, 3)
                logger.debug(f"Waiting {delay:.2f}s before retry {attempt + 1}")
                await asyncio.sleep(delay)

            # Try the original URL
            try:
                logger.debug(f"Attempting to scrape URL: {url}")
                result = await asyncio.wait_for(
                    client.async_scrape(ScrapeConfig(
                        url=url,
                        **scrape_params
                    )),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Scrape timed out after {timeout}s for {url}")
                
                # For HTTPS URLs that time out, try fallback to HTTP version
                if url.startswith('https://') and attempt == 0:
                    http_url = url.replace('https://', 'http://', 1)
                    logger.debug(f"Trying HTTP fallback for timed out HTTPS URL: {http_url}")
                    try:
                        result = await asyncio.wait_for(
                            client.async_scrape(ScrapeConfig(
                                url=http_url,
                                **scrape_params
                            )),
                            timeout=timeout
                        )
                        logger.info(f"HTTP fallback successful for {url}")
                    except asyncio.TimeoutError:
                        logger.warning(f"HTTP fallback also timed out for {http_url}")
                        if attempt < max_retries - 1:
                            continue
                        logger.error(f"Both HTTPS and HTTP attempts timed out for {url}")
                        return None
                else:
                    # Regular timeout handling for non-HTTPS URLs or after first attempt
                    if attempt < max_retries - 1:
                        continue
                    logger.error(f"Scrape timed out after {timeout}s for {url} (max retries exceeded)")
                    return None
                
            # Handle 301 redirects explicitly (for services like Namecheap URL forwarding)
            if result.response.status_code == 301:
                location = result.response.headers.get('location')
                if location:
                    logger.debug(f"Got 301 redirect from {url} to {location}, following manually")
                    try:
                        # Create a new scrape config for the redirect target
                        redirect_result = await asyncio.wait_for(
                            client.async_scrape(ScrapeConfig(
                                url=location,
                                **scrape_params
                            )),
                            timeout=timeout
                        )
                        return redirect_result
                    except asyncio.TimeoutError:
                        logger.warning(f"Redirect scrape timed out after {timeout}s for {location}")
                        if attempt < max_retries - 1:
                            continue
                        logger.error(f"Redirect scrape timed out after {timeout}s for {location} (max retries exceeded)")
                        return None

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
            return None
        except Exception as e:
            # Don't retry other exceptions
            logger.error(f"Non-retryable error for {url}: {str(e)}")
            return None

    # If we reach here, all retries failed
    return None

async def scrape_url(client: ScrapflyClient, url: str, tracker: LinkTracker, rate_limiter: RateLimiter) -> Optional[Dict]:
    """Scrape a single URL and return the result data"""
    logger.debug(f"Starting to scrape URL: {url}")
    
    # Check if URL should be excluded based on patterns
    if should_exclude_url(url, tracker.exclude_patterns):
        logger.debug(f"Skipping excluded URL: {url}")
        tracker.update_status(url, CrawlStatus.FAILED, "URL matches exclude pattern")
        return None
    
    # Skip binary content URLs
    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3', '.pdf', '.zip']):
        logger.debug(f"Skipping binary content URL: {url}")
        return None
        
    try:
        await rate_limiter.wait_if_needed()
        metadata = tracker.links.get(url, LinkMetadata(url=url))
        
        # Set default scrape parameters with explicit redirect handling
        scrape_params = {
            'asp': True,      # Enable anti-scraping protection
            'method': 'GET',  # Use GET method to handle redirects
            'render_js': metadata.render_js if metadata.render_js is not None else True,  # Enable JS rendering
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            },
            **metadata.scrape_params  # Include any existing params
        }
        
        # Remove allow_redirects as it's not a valid parameter
        if 'allow_redirects' in scrape_params:
            scrape_params.pop('allow_redirects')
        
        # Scrape with retry only for network/server errors
        result = await scrape_with_retry(client, url, scrape_params)
        
        # Check if result is None (could happen if all retries failed)
        if result is None:
            logger.error(f"Failed to get a valid result for {url} after all retries")
            tracker.update_status(url, CrawlStatus.FAILED, "Failed to get a valid result after all retries")
            return None
        
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
        
        # Track redirect chain if present
        redirect_chain = []
        if result.response.history:
            redirect_chain = [r.url for r in result.response.history]
            logger.debug(f"Followed redirect chain: {' -> '.join(redirect_chain)}")

        data = {
            "url": url,
            "final_url": result.response.url,  # The URL after following redirects
            "html": result.content,
            "metadata": {
                "status_code": metadata.status_code,
                "content_type": metadata.content_type,
                "crawled_at": metadata.crawled_at.isoformat() if metadata.crawled_at else None,
                "proxy_country": metadata.proxy_country,
                "render_js": metadata.render_js,
                "timing": metadata.timing,
                "scrape_params": metadata.scrape_params,
                "redirect_chain": redirect_chain,
                "is_redirected": bool(redirect_chain)
            }
        }

        # Extract and process links
        try:
            all_links = result.selector.css("a::attr(href)").getall()
            logger.debug(f"Found {len(all_links)} raw links on page {url}")
            
            # Filter and add new links to tracker
            filtered_links = filter_links(tracker.base_url, all_links, exclude_patterns=tracker.exclude_patterns)
            for link in filtered_links:
                if tracker.add_link(link):
                    logger.debug(f"Added new link to track: {link}")
        except Exception as e:
            logger.warning(f"Failed to extract links from {url}: {str(e)}")
                
        logger.debug(f"Prepared data for storage: {data['url']}, status: {data['metadata']['status_code']}")
        return data
        
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {str(e)}")
        tracker.update_status(url, CrawlStatus.FAILED, str(e))
        return None
