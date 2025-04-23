import logging
import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from scrapfly import ScrapflyClient
from .tracker import LinkTracker
from .rate_limiter import RateLimiter
from .scraper import scrape_url
from .utils import normalize_domain, urlparse, urlunparse

logger = logging.getLogger(__name__)

class Crawler:
    def __init__(self, api_key: str, concurrent_requests: int = 1):
        self.client = ScrapflyClient(key=api_key)
        self.concurrent_requests = concurrent_requests

    async def crawl(self, start_url: str, output_dir: Optional[str] = None, resume: bool = False) -> Tuple[Path, Path]:
        """
        Crawl a website starting from the given URL.
        
        Args:
            start_url: The URL to start crawling from
            output_dir: Optional directory to save results (defaults to './output')
            resume: Whether to attempt resuming a previous crawl
            
        Returns:
            Tuple of (output_file, state_file) Path objects
        """
        # For problematic domains like those with Namecheap URL forwarding,
        # ensure we try HTTP version first, which often works better with redirects
        if not start_url.startswith(('http://', 'https://')):
            # If no scheme specified, start with HTTP
            parsed = urlparse(f"http://{start_url}")
            normalized_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))
            logger.info(f"No scheme specified, starting with HTTP: {normalized_url}")
        else:
            # Preserve the scheme but ensure it's normalized
            parsed = urlparse(start_url)
            normalized_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))
        
        # Setup output directory
        output_dir = Path(output_dir or "output")
        output_dir.mkdir(exist_ok=True)
        
        # Create output and state filenames based on domain and date
        domain = normalize_domain(normalized_url)
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{domain}_{date_str}.jsonl"
        state_file = output_dir / f"{domain}_{date_str}.state.json"
        
        # If resuming, look for most recent state file
        if resume:
            state_files = list(output_dir.glob(f"{domain}_*.state.json"))
            if state_files:
                # Get most recent state file
                latest_state = max(state_files, key=lambda p: p.stat().st_mtime)
                logger.info(f"Resuming from state file: {latest_state}")
                state_file = latest_state
                # Update output file name to match state file
                output_file = output_dir / latest_state.name.replace('.state.json', '.jsonl')
        
        # Initialize components
        tracker = LinkTracker(normalized_url, state_file=state_file)
        rate_limiter = RateLimiter(initial_concurrency=self.concurrent_requests)
        
        logger.info(f"{'Resuming' if resume else 'Starting'} crawl of {start_url}")
        logger.debug(f"Output will be saved to: {output_file}")
        logger.debug(f"State will be saved to: {state_file}")
        
        # Open output file in append mode for resuming
        with open(output_file, 'a', encoding='utf-8') as f:
            # If not resuming, start with the normalized initial URL
            if not resume and not tracker.get_completed_links():
                result_data = await scrape_url(self.client, normalized_url, tracker, rate_limiter)
                if result_data:
                    logger.debug(f"Writing data for URL: {normalized_url}")
                    f.write(json.dumps(result_data) + '\n')
            
            # Process pending links with dynamic concurrency
            while tracker.get_pending_links():
                pending_links = list(tracker.get_pending_links())[:rate_limiter.concurrency]
                tasks = [scrape_url(self.client, url, tracker, rate_limiter) 
                        for url in pending_links]
                
                try:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Handle results and write successful ones to file
                    for result_data in results:
                        if isinstance(result_data, Exception):
                            logger.error(f"Task failed with error: {str(result_data)}")
                            continue
                        if isinstance(result_data, dict):
                            logger.debug(f"Writing data for URL: {result_data['url']}")
                            f.write(json.dumps(result_data) + '\n')
                    
                    # Add delay between batches to prevent rate limiting
                    await asyncio.sleep(random.uniform(3, 5))
                    
                except Exception as e:
                    logger.error(f"Batch processing failed: {str(e)}")
                    # Save state on error to allow resuming
                    tracker.save_state()
                    raise
        
        # Log final statistics
        logger.info(f"\nCrawl statistics for {tracker.domain}:")
        logger.info(f"Completed: {len(tracker.get_completed_links())}")
        logger.info(f"Pending: {len(tracker.get_pending_links())}")
        logger.info(f"Failed: {len(tracker.get_failed_links())}")
        logger.info(f"\nOutput saved to: {output_file}")
        logger.info(f"State saved to: {state_file}")
        
        return output_file, state_file