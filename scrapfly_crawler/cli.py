import asyncio
import sys
import os
import logging
import argparse
from dotenv import load_dotenv
from urllib.parse import urlparse
from .crawler import Crawler

def setup_logging():
    """Configure logging settings"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.getLogger("scrapfly").setLevel(logging.DEBUG)

def validate_url(url: str) -> str:
    """Validate and normalize the input URL"""
    if not url.startswith(('http://', 'https://')):
        # For unknown URLs, start with HTTP which works better with redirects
        url = 'http://' + url
        logging.info(f"No protocol specified, using HTTP for initial request: {url}")
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            raise ValueError("Invalid URL format")
        return url
    except Exception as e:
        raise ValueError(f"Invalid URL: {str(e)}")

async def main():
    """Main entry point for the CLI"""
    # Load environment variables
    load_dotenv()
    
    # Setup logging
    setup_logging()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Scrapfly web crawler')
    parser.add_argument('url', help='URL to start crawling from')
    parser.add_argument('--render-js', dest='render_js', action='store_true', 
                        help='Enable JavaScript rendering (default: False)')
    parser.add_argument('--no-render-js', dest='render_js', action='store_false',
                        help='Disable JavaScript rendering')
    parser.add_argument('--concurrent', type=int, 
                        help='Number of concurrent requests (default: from .env or 1)')
    parser.add_argument('--max-retries', type=int,
                        help='Maximum number of retry attempts (default: from .env or 3)')
    parser.add_argument('--base-delay', type=int,
                        help='Base delay between retries in seconds (default: from .env or 5)')
    parser.set_defaults(render_js=None)  # None means use the default from models.py
    
    args = parser.parse_args()
    
    try:
        # Get and validate URL
        url = validate_url(args.url)
        
        # Get API key from environment
        api_key = os.getenv('SCRAPFLY_API_KEY')
        if not api_key:
            raise ValueError("SCRAPFLY_API_KEY environment variable not set")
            
        # Get parameters from command line args, environment variables, or use defaults
        concurrent_requests = args.concurrent or int(os.getenv('CONCURRENT_REQUESTS', 1))
        max_retries = args.max_retries or int(os.getenv('MAX_RETRIES', 3))
        base_delay = args.base_delay or int(os.getenv('BASE_DELAY', 5))
        
        # These parameters will be used by RateLimiter and scrape_with_retry
        os.environ['INITIAL_CONCURRENCY'] = str(concurrent_requests)
        os.environ['MIN_CONCURRENCY'] = os.getenv('MIN_CONCURRENCY', '1')
        os.environ['MAX_CONCURRENCY'] = os.getenv('MAX_CONCURRENCY', str(concurrent_requests))
        os.environ['BASE_DELAY'] = str(base_delay)
        os.environ['MAX_RETRIES'] = str(max_retries)
        
        # Set render_js environment variable if specified in command line
        if args.render_js is not None:
            os.environ['RENDER_JS'] = str(args.render_js).lower()
        
        # Create and run crawler
        crawler = Crawler(api_key=api_key, concurrent_requests=concurrent_requests)
        output_file = await crawler.crawl(url)
        
        print(f"\nCrawling completed. Output saved to: {output_file}")
        
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
