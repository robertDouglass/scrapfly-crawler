#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Set
from collections import defaultdict
from urllib.parse import urlparse

# Import only what we need
from enum import Enum
from dataclasses import dataclass
from typing import Optional

# Minimal implementations of required classes
class CrawlStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class LinkMetadata:
    url: str
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    crawled_at: Optional[datetime] = None
    error: Optional[str] = None
    proxy_country: Optional[str] = None
    render_js: Optional[bool] = None
    timing: Optional[Dict] = None
    scrape_params: Dict = None
    final_url: Optional[str] = None
    redirect_chain: Optional[list] = None
    is_redirected: bool = False

def get_domain(url: str) -> str:
    """Extract domain from URL"""
    return urlparse(url).netloc

class LinkTracker:
    def __init__(self, base_url: str, state_file: Optional[Path] = None):
        self.base_url = base_url
        self.domain = get_domain(base_url)
        self.links: Dict[str, LinkMetadata] = {}
        self.status: Dict[str, CrawlStatus] = {}
        self.discovered_at: Dict[str, datetime] = {}
        self.state_file = state_file

    def add_link(self, url: str) -> bool:
        """Add a new link to track. Returns True if link was added, False if it already exists."""
        if url in self.links:
            return False
            
        self.links[url] = LinkMetadata(url=url)
        self.status[url] = CrawlStatus.PENDING
        self.discovered_at[url] = datetime.now()
        return True

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

def process_jsonl_files(output_dir: Path) -> Dict[str, Set[dict]]:
    """Process all JSONL files and group entries by domain"""
    domain_entries = defaultdict(set)
    
    for jsonl_file in output_dir.glob("*.jsonl"):
        with jsonl_file.open() as f:
            for line in f:
                entry = json.loads(line)
                url = entry.get("url")
                if url:
                    domain = get_domain(url)
                    domain_entries[domain].add(json.dumps(entry))  # Use JSON string as it's hashable
                    
    return domain_entries

def create_state_files(output_dir: Path):
    """Create state files for each domain from JSONL files"""
    domain_entries = process_jsonl_files(output_dir)
    
    for domain, entries in domain_entries.items():
        # Create state file path
        state_file = output_dir / f"{domain}.state.json"
        
        # Initialize tracker with first URL for the domain
        first_entry = json.loads(next(iter(entries)))
        tracker = LinkTracker(first_entry["url"], state_file)
        
        # Process all entries for this domain
        for entry_json in entries:
            entry = json.loads(entry_json)
            url = entry["url"]
            
            # Create metadata
            metadata = LinkMetadata(url=url)
            metadata.status_code = entry.get("status_code")
            metadata.content_type = entry.get("content_type")
            metadata.crawled_at = datetime.fromisoformat(entry["timestamp"]) if "timestamp" in entry else datetime.now()
            metadata.final_url = entry.get("final_url", url)
            metadata.is_redirected = bool(entry.get("redirect_chain"))
            metadata.redirect_chain = entry.get("redirect_chain", [])
            
            # Add link and update metadata
            tracker.add_link(url)
            tracker.links[url] = metadata
            tracker.status[url] = CrawlStatus.COMPLETED
            tracker.discovered_at[url] = metadata.crawled_at
            
            # If there was a redirect, add the final URL
            if metadata.is_redirected and get_domain(metadata.final_url) == domain:
                tracker.add_link(metadata.final_url)
        
        # Save state file
        tracker.save_state()
        print(f"Created state file: {state_file}")

def main():
    output_dir = Path(__file__).parent.parent / "output"
    if not output_dir.exists():
        print(f"Output directory not found: {output_dir}")
        return
        
    create_state_files(output_dir)
    print("State files generated successfully")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        exit(1)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)