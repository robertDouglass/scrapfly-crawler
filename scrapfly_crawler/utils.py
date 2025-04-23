from urllib.parse import urlparse, urljoin, urldefrag, parse_qs, urlencode, urlunparse
from typing import Set, List, Optional

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
        '/assets/', '/_assets/', '/static/', '/media/',
        '/dist/', '/build/', '/vendor/',
        'fonts.googleapis.com',
        'ajax.googleapis.com'
    ]
    return any(pattern in url for pattern in skip_patterns)

def should_exclude_url(url: str, exclude_patterns: Optional[List[str]] = None) -> bool:
    """Check if URL should be excluded based on custom exclude patterns"""
    if not exclude_patterns:
        return False
        
    parsed = urlparse(url)
    
    # Check if any exclude pattern exists in the URL path
    for pattern in exclude_patterns:
        if pattern in parsed.path:
            return True
            
    return False
    
def normalize_query_params(url: str) -> str:
    """Normalize URL by removing or standardizing certain query parameters"""
    # Parameters that should be removed as they don't affect content
    skip_params = {
        # Analytics
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        # Cache busters
        'timestamp', 'ts', 't', 'rand', 'random',
        # Common tracking params
        'fbclid', 'gclid', 'msclkid',
        # Session/click IDs that don't affect content
        '_hsenc', '_hsmi', 'mc_cid', 'mc_eid',
    }
    
    parsed = urlparse(url)
    if not parsed.query:
        return url
        
    # Parse query parameters
    params = parse_qs(parsed.query, keep_blank_values=True)
    
    # Remove skipped parameters
    filtered_params = {k: v for k, v in params.items() if k.lower() not in skip_params}
    
    # Reconstruct URL with filtered parameters
    new_query = urlencode(filtered_params, doseq=True) if filtered_params else ''
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        ''  # Remove fragment as it's handled separately
    ))

def strip_url_fragment(url: str) -> str:
    """Remove fragment/anchor from URL"""
    return urldefrag(url)[0]


def normalize_url(base_url: str, link: str) -> str:
    """Convert relative URL to absolute URL"""
    return urljoin(base_url, link)
def normalize_domain(domain: str) -> str:
    """Extract base domain without normalization"""
    return domain.lower()  # Just lowercase for consistency

def get_domain(url: str) -> str:
    """Extract and normalize domain from URL"""
    domain = urlparse(url).netloc
    return normalize_domain(domain)


def filter_links(base_url: str, links: Set[str], exclude_patterns: Optional[List[str]] = None) -> Set[str]:
    """Filter and normalize a set of links"""
    domain = get_domain(base_url)
    normalized_links = set()
    
    for link in links:
        if not link:  # Skip empty links
            continue
            
        # Convert relative to absolute URL
        absolute_url = normalize_url(base_url, link)
        # Normalize query parameters and strip fragment
        clean_url = normalize_query_params(absolute_url)
        clean_url = strip_url_fragment(clean_url)
        parsed_link = urlparse(clean_url)
        
        # Skip URLs matching exclude patterns
        if should_exclude_url(clean_url, exclude_patterns):
            continue
        
        # Skip resource URLs and only keep links from the same domain
        link_domain = normalize_domain(parsed_link.netloc)
        base_domain = normalize_domain(domain)
        if not is_resource_url(clean_url) and link_domain == base_domain:
            # Keep original scheme
            normalized_links.add(clean_url)
            
    return normalized_links