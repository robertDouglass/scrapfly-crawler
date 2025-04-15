# Scrapfly Crawler

A robust web crawler implementation using the Scrapfly API for handling JavaScript rendering, proxy rotation, and rate limiting.

## Features

- Intelligent URL and redirect handling
  - Automatic following of 301/302 redirects
  - Smart handling of www/non-www domains
  - Protocol (http/https) preservation unless redirected
- Automatic JavaScript rendering with configurable rendering options
- Smart rate limiting and concurrency control
  - Auto-adjusting concurrency based on response codes
  - Respects server's retry-after headers
  - Exponential backoff for failed requests
- Proxy rotation through Scrapfly
- Recursive crawling with domain filtering
- JSONL output format with detailed metadata
- Configurable through environment variables
- Robust error handling and retries
  - Automatic retries with exponential backoff
  - Smart handling of binary content (images, videos, etc.)
  - Different retry strategies for different status codes

## Installation

```bash
pip install scrapfly-crawler
```

## Usage

### Command Line Interface

```bash
# Set your Scrapfly API key in .env file or environment
export SCRAPFLY_API_KEY='your-api-key'

# Basic usage
scrapfly-crawler https://example.com

# Advanced usage with all options
scrapfly-crawler https://example.com \
    --concurrent 2 \        # Number of concurrent requests
    --max-retries 3 \      # Maximum retry attempts
    --base-delay 5 \       # Base delay between retries (seconds)
    --render-js \          # Enable JavaScript rendering
    --no-render-js \       # Disable JavaScript rendering (default)
```

### URL and Redirect Handling

The crawler implements smart URL and redirect handling:

- Follows 301/302 redirects automatically
- Preserves original URL schemes (http/https) unless redirected
- Handles www and non-www domains through redirects
- Defaults to http:// for URLs without a protocol

### JavaScript Rendering Options

The crawler provides three ways to control JavaScript rendering:

1. Use neither flag: Uses the default from configuration (RENDER_JS environment variable)
2. Use `--render-js`: Explicitly enables JavaScript rendering
3. Use `--no-render-js`: Explicitly disables JavaScript rendering

This three-state design allows you to use the default configuration for normal usage while providing explicit overrides when needed.

### Python API

```python
import asyncio
from scrapfly_crawler import Crawler

async def main():
    # Initialize the crawler
    crawler = Crawler(
        api_key='your-api-key',
        concurrent_requests=1
    )
    
    # Start crawling
    output_file = await crawler.crawl('https://example.com')
    print(f"Crawl completed. Output saved to: {output_file}")

# Run the crawler
asyncio.run(main())
```

## Environment Variables
- `SCRAPFLY_API_KEY`: Your Scrapfly API key (required)
- `CONCURRENT_REQUESTS`: Initial number of concurrent requests (default: 1)
- `MIN_CONCURRENCY`: Minimum number of concurrent requests during auto-adjustment (default: 1)
- `MAX_CONCURRENCY`: Maximum number of concurrent requests during auto-adjustment (default: same as CONCURRENT_REQUESTS)
- `MAX_RETRIES`: Maximum number of retry attempts for failed requests (default: 3)
- `BASE_DELAY`: Base delay between retries in seconds (default: 10)
- `RENDER_JS`: Enable/disable JavaScript rendering (default: false)

Note: The `INITIAL_CONCURRENCY` variable is set internally based on the `CONCURRENT_REQUESTS` value and should not be set manually.

### Metadata Tracking

For each crawled URL, the following metadata is tracked:

- URL
- HTTP status code
- Content type
- Timestamp of crawl
- Error message (if any)
- Proxy country used
- JavaScript rendering status
- Request/response timing information

### Crawl Statuses

URLs can have the following statuses during crawling:

- `pending`: URL is queued for crawling
- `in_progress`: URL is currently being crawled
- `completed`: URL has been successfully crawled
- `failed`: URL crawling failed after all retries

### Default Scraping Parameters

The crawler uses modern browser headers and the following default parameters:

- JavaScript rendering: disabled by default (configurable)
- Anti-scraping protection bypass: enabled
- Debug mode: enabled
- Modern Chrome User-Agent and headers
- Gzip/Deflate/Brotli compression support
- Cache-Control: no-cache

The crawler features smart concurrency adjustment:
- Starts with CONCURRENT_REQUESTS (or INITIAL_CONCURRENCY) parallel requests
- Automatically scales between MIN_CONCURRENCY and MAX_CONCURRENCY based on response success/failure
- Reduces concurrency on errors or rate limits
- Gradually increases concurrency when requests succeed
- Maintains optimal crawl speed while respecting site limits


## Output Format

The crawler saves results in JSONL format with each line containing:

```json
{
    "url": "https://example.com",
    "html": "<html>...</html>",         # HTML content for text/html responses
                                       # null for binary content (images, videos, etc.)
                                       # null for failed requests
    "metadata": {
        "status_code": 200,             # HTTP status code of the response
        "content_type": "text/html",    # Content-Type header from response
                                       # e.g. "image/jpeg", "video/mp4", etc.
        "crawled_at": "2025-04-14T12:30:00",
        "proxy_country": "us",          # Country of proxy used (if any)
        "render_js": true,              # Whether JavaScript was rendered
        "timing": {                     # Request timing information
            "start": "2025-04-14T12:30:00.123",
            "end": "2025-04-14T12:30:01.456",
            "duration_ms": 1333
        },
        "scrape_params": {
            "render_js": true,
            "asp": true,
            "debug": true,
            "headers": {
                "User-Agent": "...",
                ...
            }
        }
    }
}
```

## Error Handling

The crawler implements sophisticated error handling:

- Binary content (images, videos, etc.) is detected via Content-Type and handled appropriately
- 4xx client errors are not retried (except 429 rate limit responses)
- 5xx server errors are retried with exponential backoff
- Rate limit (429) responses respect the server's retry-after header
- Each URL has configurable max retries and base delay between retries
- Exponential backoff increases delay between retries: base_delay * (2 ^ attempt)

## Development

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -e .
   ```

Note: The package requires Python 3.7 or later and has the following main dependencies:
- scrapfly-sdk>=0.8.5
- python-dotenv>=0.19.0
- aiohttp>=3.8.0

### Version Control

The following files and directories are excluded from version control:

- Python build artifacts (`__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`, `build/`, `dist/`, `*.egg-info/`)
- Virtual environments (`.venv/`, `env/`, `venv/`)
- Environment files (`.env`)
- IDE configuration files (`.idea/`, `.vscode/`)
- Project output files (`output/`, `*.jsonl`)

## License

MIT License - see LICENSE file for details.