import os
import sys
import logging
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv
from .crawler import Crawler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

def get_api_key() -> str:
    """Get Scrapfly API key from environment variable"""
    api_key = os.getenv('SCRAPFLY_API_KEY')
    if not api_key:
        logger.error("SCRAPFLY_KEY environment variable not set")
        sys.exit(1)
    return api_key

async def main() -> None:
    parser = argparse.ArgumentParser(description='Crawl a website using Scrapfly')
    parser.add_argument('url', help='URL to start crawling from')
    parser.add_argument('--output-dir', '-o', help='Directory to save output files', default='output')
    parser.add_argument('--concurrent', '-c', type=int, help='Number of concurrent requests', default=1)
    parser.add_argument('--resume', '-r', action='store_true', help='Resume from previous crawl state')
    parser.add_argument('--exclude-patterns', '-e', nargs='+', help='URL patterns to exclude from crawling (e.g., "/and/" "/or/")', default=[])
    
    args = parser.parse_args()
    
    # Create crawler instance
    crawler = Crawler(
        api_key=get_api_key(),
        concurrent_requests=args.concurrent
    )
    
    try:
        # Start crawling
        output_file, state_file = await crawler.crawl(
            start_url=args.url,
            output_dir=args.output_dir,
            resume=args.resume,
            exclude_patterns=args.exclude_patterns
        )
        logger.info(f"Crawl completed successfully")
        
    except KeyboardInterrupt:
        logger.info("\nCrawl interrupted by user")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Crawl failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
