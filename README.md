# Scrapfly Crawler

A robust web crawler implementation using the Scrapfly API for handling JavaScript rendering, proxy rotation, and rate limiting.

## Features

- Intelligent URL and redirect handling
  - Automatic following of 301/302 redirects
  - Smart handling of www/non-www domains
  - Protocol (http/https) preservation unless redirected
- URL filtering and exclusion
  - Exclude URLs that match specific patterns
  - Pattern exclusion works during discovery and before processing
  - Exclusion patterns persist in state files for resumed crawls
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
- Resume interrupted crawls
  - Automatic state persistence
  - Resume from last known position
  - Handles interruptions gracefully
  - Maintains crawl progress across sessions

## Installation

1. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

2. Install in development mode:
```bash
pip install -e .
```

## Usage

### Command Line Interface

```bash
# Set your Scrapfly API key in .env file or environment
export SCRAPFLY_API_KEY='your-api-key'

# Basic usage (as module)
python -m scrapfly_crawler.cli https://example.com

# Resume an interrupted crawl
python -m scrapfly_crawler.cli https://example.com --resume

# Exclude specific URL patterns
python -m scrapfly_crawler.cli https://example.com --exclude-patterns "/and/" "/or/"

# Alternative usage (if console script is in PATH)
scrapfly-crawler https://example.com

# Advanced usage with all options
python -m scrapfly_crawler.cli https://example.com \
    --concurrent 2 \        # Number of concurrent requests
    --max-retries 3 \      # Maximum retry attempts
    --base-delay 5 \       # Base delay between retries (seconds)
    --render-js \          # Enable JavaScript rendering
    --no-render-js \       # Disable JavaScript rendering (default)
    --resume \             # Resume from previous state
    --exclude-patterns "/and/" "/path/to/exclude/" # Exclude URL patterns
```

### URL Pattern Exclusion

The crawler supports excluding URLs based on patterns:

- Specify one or more patterns with `--exclude-patterns` (or `-e`)
- Any URL containing the specified patterns in its path will be excluded
- Exclusion happens at multiple stages:
  - When loading a state file (for resuming crawls)
  - When discovering new links
  - Before processing any URL
- Exclude patterns are saved in the state file
- When resuming a crawl:
  - Command-line exclude patterns take precedence
  - If no patterns are specified, patterns from the state file are used
- Statistics about excluded URLs are tracked and displayed

Example usage:
```bash
# Exclude URLs containing "/and/" or "/category/" in their paths
python -m scrapfly_crawler.cli https://example.com --exclude-patterns "/and/" "/category/"
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
    
    # Start new crawl
    output_file, state_file = await crawler.crawl('https://example.com')
    print(f"Crawl completed. Output saved to: {output_file}")
    
    # Start new crawl with exclude patterns
    output_file, state_file = await crawler.crawl(
        'https://example.com',
        exclude_patterns=['/and/', '/category/']
    )
    print(f"Crawl completed. Output saved to: {output_file}")
    
    # Resume interrupted crawl
    output_file, state_file = await crawler.crawl('https://example.com', resume=True)
    print(f"Crawl resumed and completed. Output saved to: {output_file}")
    
    # Resume interrupted crawl with exclude patterns
    output_file, state_file = await crawler.crawl(
        'https://example.com',
        resume=True,
        exclude_patterns=['/and/', '/category/']
    )
    print(f"Crawl resumed with exclude patterns. Output saved to: {output_file}")

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

The crawler generates two types of files:

1. JSONL output file containing scraped data:
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

2. State file (.state.json) for resuming interrupted crawls:
```json
{
    "base_url": "https://example.com",
    "domain": "example.com",
    "exclude_patterns": ["/and/", "/category/"],
    "excluded_count": 42,
    "links": {
        "https://example.com/page1": {
            "url": "https://example.com/page1",
            "status_code": 200,
            "content_type": "text/html",
            "crawled_at": "2025-04-14T12:30:00",
            ...
        },
        ...
    },
    "status": {
        "https://example.com/page1": "completed",
        "https://example.com/page2": "pending",
        ...
    },
    "discovered_at": {
        "https://example.com/page1": "2025-04-14T12:30:00",
        ...
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
- Interruptions are handled gracefully with state persistence

### Resuming Interrupted Crawls

The crawler supports resuming interrupted crawls:

1. State is automatically saved after each URL update
2. When interrupted (Ctrl+C, error, etc.), state is preserved
3. Use `--resume` flag to continue from last known position
4. Most recent state file for domain is automatically detected
5. New results are appended to existing output file
6. Progress is maintained across sessions

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
- Project output files (`output/`, `*.jsonl`, `*.state.json`)

## License

MIT License - see LICENSE file for details.