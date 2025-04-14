import logging
import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from scrapfly import ScrapflyClient
from .tracker import LinkTracker
from .rate_limiter import RateLimiter
from .scraper import scrape_url

logger = logging.getLogger(__name__)

class Crawler:
    def __init__(self, api_key: str, concurrent_requests: int = 1):
        self.client = ScrapflyClient(key=api_key)
        self.concurrent_requests = concurrent_requests

    async def crawl(self, start_url: str, output_dir: Optional[str] = None) -> Path:
        """
        Crawl a website starting from the given URL.
        
        Args:
            start_url: The URL to start crawling from
            output_dir: Optional directory to save results (defaults to './output')
            
        Returns:
            Path object pointing to the output file
        """
        # Initialize components
        tracker = LinkTracker(start_url)
        rate_limiter = RateLimiter(initial_concurrency=self.concurrent_requests)
        
        # Setup output directory
        output_dir = Path(output_dir or "output")
        output_dir.mkdir(exist_ok=True)
        
        # Create output filename based on domain and date
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{tracker.domain}_{date_str}.jsonl"
        
        logger.info(f"Starting crawl of {start_url}")
        logger.debug(f"Output will be saved to: {output_file}")
        
        # Open output file and start crawling
        with open(output_file, 'w', encoding='utf-8') as f:
            # First scrape the initial URL
            result_data = await scrape_url(self.client, start_url, tracker, rate_limiter)
            if result_data:
                logger.debug(f"Writing data for URL: {start_url}")
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
        
        # Log final statistics
        logger.info(f"\nCrawl statistics for {tracker.domain}:")
        logger.info(f"Completed: {len(tracker.get_completed_links())}")
        logger.info(f"Pending: {len(tracker.get_pending_links())}")
        logger.info(f"Failed: {len(tracker.get_failed_links())}")
        logger.info(f"\nOutput saved to: {output_file}")
        
        return output_file