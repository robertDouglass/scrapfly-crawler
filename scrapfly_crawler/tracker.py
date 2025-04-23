from datetime import datetime
import json
from pathlib import Path
from typing import Dict, Set, Optional
from .models import LinkMetadata, CrawlStatus
from .utils import get_domain, strip_url_fragment, normalize_query_params

class LinkTracker:
    def __init__(self, base_url: str, state_file: Optional[Path] = None):
        self.base_url = base_url
        self.domain = get_domain(base_url)
        self.links: Dict[str, LinkMetadata] = {}
        self.status: Dict[str, CrawlStatus] = {}
        self.discovered_at: Dict[str, datetime] = {}
        self.state_file = state_file
        
        # Load existing state if provided
        if state_file and state_file.exists():
            self.load_state(state_file)
            
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
        
        # Save state after adding new link
        if self.state_file:
            self.save_state()
            
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
        
        # Save state after updating link
        if self.state_file:
            self.save_state()
        
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
            
            # Save state after status update
            if self.state_file:
                self.save_state()
                
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

    def save_state(self) -> None:
        """Save current state to file"""
        if not self.state_file:
            return
            
        state = {
            'base_url': self.base_url,
            'domain': self.domain,
            'links': {
                url: {
                    'url': metadata.url,
                    'status_code': metadata.status_code,
                    'content_type': metadata.content_type,
                    'crawled_at': metadata.crawled_at.isoformat() if metadata.crawled_at else None,
                    'error': metadata.error,
                    'proxy_country': metadata.proxy_country,
                    'render_js': metadata.render_js,
                    'timing': metadata.timing,
                    'scrape_params': metadata.scrape_params,
                    'final_url': metadata.final_url,
                    'redirect_chain': metadata.redirect_chain,
                    'is_redirected': metadata.is_redirected
                }
                for url, metadata in self.links.items()
            },
            'status': {url: status.value for url, status in self.status.items()},
            'discovered_at': {url: dt.isoformat() for url, dt in self.discovered_at.items()}
        }
        
        self.state_file.write_text(json.dumps(state))

    def load_state(self, state_file: Path) -> None:
        """Load state from file"""
        state = json.loads(state_file.read_text())
        
        self.base_url = state['base_url']
        self.domain = state['domain']
        
        # Restore links
        self.links = {}
        for url, link_data in state['links'].items():
            metadata = LinkMetadata(url=link_data['url'])
            metadata.status_code = link_data['status_code']
            metadata.content_type = link_data['content_type']
            metadata.crawled_at = datetime.fromisoformat(link_data['crawled_at']) if link_data['crawled_at'] else None
            metadata.error = link_data['error']
            metadata.proxy_country = link_data['proxy_country']
            metadata.render_js = link_data['render_js']
            metadata.timing = link_data['timing']
            metadata.scrape_params = link_data['scrape_params']
            metadata.final_url = link_data['final_url']
            metadata.redirect_chain = link_data['redirect_chain']
            metadata.is_redirected = link_data['is_redirected']
            self.links[url] = metadata
            
        # Restore status
        self.status = {url: CrawlStatus(status) for url, status in state['status'].items()}
        
        # Restore discovered_at
        self.discovered_at = {url: datetime.fromisoformat(dt) for url, dt in state['discovered_at'].items()}