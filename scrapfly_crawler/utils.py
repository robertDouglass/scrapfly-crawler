from urllib.parse import urlparse, urljoin
from typing import Set

def is_resource_url(url: str) -> bool:
    """Check if URL is a resource that should be skipped"""
    url = url.lower()
    # Add more extensions to skip
    skip_extensions = {
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp',
        # Web resources
        '.js', '.css', '.map',
        # Fonts
        '.woff', '.woff2', '.ttf', '.eot', '.otf',
        # Documents
        '.pdf', '.doc', '.docx',
        # Data
        '.json', '.xml',
        # Media
        '.mp4', '.webm', '.mp3', '.wav',
        # Archives
        '.zip', '.tar', '.gz'
    }
    # Check file extensions
    if any(url.endswith(ext) for ext in skip_extensions):
        return True
    # Check URL patterns
    skip_patterns = [
        '/assets/', '/static/', '/media/',
        '/dist/', '/build/', '/vendor/',
        'fonts.googleapis.com',
        'ajax.googleapis.com'
    ]
    return any(pattern in url for pattern in skip_patterns)

def normalize_url(base_url: str, link: str) -> str:
    """Convert relative URL to absolute URL"""
    return urljoin(base_url, link)

def get_domain(url: str) -> str:
    """Extract domain from URL"""
    return urlparse(url).netloc

def filter_links(base_url: str, links: Set[str]) -> Set[str]:
    """Filter and normalize a set of links"""
    domain = get_domain(base_url)
    normalized_links = set()
    
    for link in links:
        if not link:  # Skip empty links
            continue
            
        # Convert relative to absolute URL
        absolute_url = normalize_url(base_url, link)
        parsed_link = urlparse(absolute_url)
        
        # Skip resource URLs and only keep links from the same domain
        if not is_resource_url(absolute_url) and parsed_link.netloc == domain:
            normalized_links.add(absolute_url)
            
    return normalized_links