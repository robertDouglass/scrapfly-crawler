from datetime import datetime
from typing import Dict, Set, Optional
from .models import LinkMetadata, CrawlStatus
from .utils import get_domain, strip_url_fragment, normalize_query_params

class LinkTracker:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.domain = get_domain(base_url)
        self.links: Dict[str, LinkMetadata] = {}
        self.status: Dict[str, CrawlStatus] = {}
        self.discovered_at: Dict[str, datetime] = {}
        
    def add_link(self, url: str) -> bool:
        """Add a new link to track. Returns True if link was added, False if it already exists."""
        # Normalize query parameters and strip fragment
        clean_url = normalize_query_params(url)
        clean_url = strip_url_fragment(clean_url)
        if clean_url in self.links:
            return False
            
        self.links[clean_url] = LinkMetadata(url=clean_url)
        self.status[clean_url] = CrawlStatus.PENDING
        self.discovered_at[clean_url] = datetime.now()
        return True
        
    def update_from_result(self, result, url: str, scrape_params: Dict = None) -> None:
        """Update link metadata from a scrape result"""
        clean_url = normalize_query_params(url)
        clean_url = strip_url_fragment(clean_url)
        if clean_url not in self.links:
            self.add_link(clean_url)
            
        metadata = self.links[clean_url]
        metadata.status_code = result.response.status_code
        metadata.content_type = result.response.headers.get("content-type")
        metadata.crawled_at = datetime.now()
        
        # Track redirect information
        if result.response.history:
            metadata.is_redirected = True
            metadata.redirect_chain = [r.url for r in result.response.history]
            metadata.final_url = result.response.url
        else:
            metadata.is_redirected = False
            metadata.redirect_chain = []
            metadata.final_url = clean_url
        
        if scrape_params:
            metadata.scrape_params = scrape_params
            metadata.render_js = scrape_params.get("render_js", False)
            
        self.links[clean_url] = metadata
        self.status[clean_url] = CrawlStatus.COMPLETED
        
        # If URL was redirected, add the final URL to tracking if it's on the same domain
        if metadata.is_redirected and get_domain(metadata.final_url) == self.domain:
            final_clean_url = normalize_query_params(metadata.final_url)
            final_clean_url = strip_url_fragment(final_clean_url)
            if final_clean_url not in self.links:
                self.add_link(final_clean_url)

    def get_all_links(self) -> Set[str]:
        """Get all tracked links regardless of status"""
        return set(self.links.keys())
        
    def update_status(self, url: str, status: CrawlStatus, error: Optional[str] = None) -> None:
        """Update the status of a link"""
        clean_url = normalize_query_params(url)
        clean_url = strip_url_fragment(clean_url)
        if clean_url in self.links:
            self.status[clean_url] = status
            if error:
                self.links[clean_url].error = error
                
    def get_pending_links(self) -> Set[str]:
        """Get all links that haven't been crawled yet"""
        return {url for url, status in self.status.items()
                if status == CrawlStatus.PENDING}
                
    def get_failed_links(self) -> Set[str]:
        """Get all links that failed to crawl"""
        return {url for url, status in self.status.items()
                if status == CrawlStatus.FAILED}
                
    def get_completed_links(self) -> Set[str]:
        """Get all successfully crawled links"""
        return {url for url, status in self.status.items()
                if status == CrawlStatus.COMPLETED}