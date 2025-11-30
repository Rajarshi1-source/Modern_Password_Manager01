"""
Scrapy Spiders for Dark Web Content Scraping

Supports:
- Tor/SOCKS5 proxy
- Multiple source types (forums, pastebin, marketplaces)
- Breach data extraction
- Rate limiting and politeness
"""

import scrapy
from scrapy import signals
from scrapy.exceptions import DropItem
import re
import logging
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class BreachForumSpider(scrapy.Spider):
    """
    Spider for scraping breach-related forums
    
    Extracts:
    - Post titles
    - Post content
    - Author information
    - Timestamps
    - Links to breach data
    """
    
    name = 'breach_forum'
    allowed_domains = []  # Will be set dynamically
    custom_settings = {
        'DOWNLOAD_DELAY': 5,  # 5 seconds between requests
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'RETRY_TIMES': 3,
        'DOWNLOAD_TIMEOUT': 30,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'ROBOTSTXT_OBEY': False,  # Dark web sites don't typically have robots.txt
        'HTTPCACHE_ENABLED': True,
        'HTTPCACHE_EXPIRATION_SECS': 3600,  # Cache for 1 hour
    }
    
    def __init__(self, url=None, use_tor=True, source_id=None, *args, **kwargs):
        """
        Initialize spider
        
        Args:
            url: Starting URL to scrape
            use_tor: Whether to use Tor proxy
            source_id: Database ID of the source
        """
        super().__init__(*args, **kwargs)
        self.start_urls = [url] if url else []
        self.use_tor = use_tor
        self.source_id = source_id
        
        # Set proxy settings
        if use_tor:
            self.custom_settings['DOWNLOADER_MIDDLEWARES'] = {
                'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 750,
            }
    
    def start_requests(self):
        """Generate initial requests with proxy settings"""
        for url in self.start_urls:
            meta = {}
            
            if self.use_tor:
                # Use Tor SOCKS5 proxy
                meta['proxy'] = 'socks5h://localhost:9050'
            
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta=meta,
                errback=self.errback_httpbin
            )
    
    def parse(self, response):
        """
        Parse forum page and extract breach data
        
        Override this method for specific forum structures
        """
        logger.info(f"Parsing {response.url}")
        
        # Generic extraction (override for specific forums)
        # Try to find posts/threads
        posts = response.css('.post, .thread, .message, article')
        
        if not posts:
            # Try alternative selectors
            posts = response.xpath('//div[contains(@class, "post") or contains(@class, "thread")]')
        
        for post in posts:
            try:
                item = self.extract_post_data(post, response)
                if item:
                    yield item
            except Exception as e:
                logger.error(f"Error extracting post: {e}")
                continue
        
        # Follow pagination links
        next_page = response.css('a.next, a.pagination-next, .next-page::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)
    
    def extract_post_data(self, post_selector, response):
        """
        Extract structured data from a post
        
        Args:
            post_selector: Scrapy selector for the post
            response: Scrapy response object
        
        Returns:
            dict: Extracted breach data
        """
        # Extract title
        title = post_selector.css('.title::text, h2::text, h3::text').get()
        if not title:
            title = post_selector.xpath('.//h2/text() | .//h3/text() | .//strong/text()').get()
        
        # Extract content
        content = post_selector.css('.content::text, .message::text, p::text').getall()
        content_text = ' '.join(content).strip() if content else ''
        
        # Extract author
        author = post_selector.css('.author::text, .username::text').get()
        
        # Extract timestamp
        timestamp = post_selector.css('.timestamp::text, .date::text, time::text').get()
        
        # Extract links
        links = post_selector.css('a::attr(href)').getall()
        
        # Only yield if we have meaningful content
        if not title and not content_text:
            return None
        
        return {
            'type': 'breach_forum_post',
            'source_url': response.url,
            'source_id': self.source_id,
            'title': title.strip() if title else '',
            'content': content_text[:5000],  # Limit content length
            'author': author.strip() if author else '',
            'timestamp': timestamp.strip() if timestamp else '',
            'links': links[:10],  # Limit number of links
            'scraped_at': datetime.now().isoformat(),
            'indicators': self.extract_breach_indicators(title, content_text)
        }
    
    def extract_breach_indicators(self, title, content):
        """
        Extract breach-related indicators from text
        
        Returns:
            dict: Extracted indicators (emails, domains, keywords)
        """
        text = f"{title} {content}".lower()
        
        indicators = {
            'emails_found': len(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)),
            'domains_found': len(re.findall(r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]\b', text)),
            'has_password_keyword': any(kw in text for kw in ['password', 'passwd', 'pwd', 'credentials']),
            'has_breach_keyword': any(kw in text for kw in ['breach', 'leak', 'dump', 'database', 'hacked']),
            'has_personal_data': any(kw in text for kw in ['ssn', 'social security', 'credit card', 'dob', 'date of birth']),
            'has_financial_data': any(kw in text for kw in ['bank', 'account', 'credit', 'debit', 'payment']),
        }
        
        return indicators
    
    def errback_httpbin(self, failure):
        """Handle request failures"""
        logger.error(f"Request failed: {failure.request.url} - {failure.value}")
        
        # You can implement retry logic or error reporting here


class PastebinSpider(scrapy.Spider):
    """
    Spider for scraping pastebin-style sites
    
    Extracts:
    - Paste titles
    - Paste content
    - Raw text dumps
    """
    
    name = 'pastebin'
    
    custom_settings = {
        'DOWNLOAD_DELAY': 3,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'RETRY_TIMES': 2,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    def __init__(self, url=None, use_tor=True, source_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = [url] if url else []
        self.use_tor = use_tor
        self.source_id = source_id
    
    def start_requests(self):
        """Generate initial requests"""
        for url in self.start_urls:
            meta = {}
            if self.use_tor:
                meta['proxy'] = 'socks5h://localhost:9050'
            
            yield scrapy.Request(url, callback=self.parse, meta=meta)
    
    def parse(self, response):
        """Parse pastebin page"""
        logger.info(f"Parsing pastebin: {response.url}")
        
        # Extract paste content
        title = response.css('h1::text, .paste-title::text').get()
        content = response.css('textarea::text, .paste-content::text, pre::text').get()
        
        if not content:
            # Try alternative extraction
            content = response.xpath('//textarea/text() | //pre/text()').get()
        
        if content:
            yield {
                'type': 'pastebin',
                'source_url': response.url,
                'source_id': self.source_id,
                'title': title.strip() if title else '',
                'content': content[:10000],  # Limit to 10KB
                'scraped_at': datetime.now().isoformat(),
                'indicators': self.extract_breach_indicators(content)
            }
        
        # Follow links to other pastes
        paste_links = response.css('a.paste-link::attr(href), .archive-list a::attr(href)').getall()
        for link in paste_links[:50]:  # Limit crawling
            yield response.follow(link, callback=self.parse)
    
    def extract_breach_indicators(self, content):
        """Extract breach indicators from paste content"""
        indicators = {
            'line_count': len(content.split('\n')),
            'has_credentials': bool(re.search(r'[\w\.-]+@[\w\.-]+:\S+', content)),
            'has_email_format': bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)),
            'has_hash_format': bool(re.search(r'\b[a-fA-F0-9]{32,64}\b', content)),
        }
        return indicators


class GenericDarkWebSpider(scrapy.Spider):
    """
    Generic spider for dark web content
    
    Can adapt to different site structures
    """
    
    name = 'generic_darkweb'
    
    custom_settings = {
        'DOWNLOAD_DELAY': 5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'DEPTH_LIMIT': 3,  # Don't crawl too deep
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    def __init__(self, url=None, use_tor=True, source_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = [url] if url else []
        self.use_tor = use_tor
        self.source_id = source_id
    
    def start_requests(self):
        """Generate initial requests"""
        for url in self.start_urls:
            meta = {}
            if self.use_tor:
                meta['proxy'] = 'socks5h://localhost:9050'
            
            yield scrapy.Request(url, callback=self.parse, meta=meta)
    
    def parse(self, response):
        """Generic parsing logic"""
        logger.info(f"Parsing generic site: {response.url}")
        
        # Extract all text content
        text_content = ' '.join(response.css('p::text, div::text, span::text').getall())
        
        # Check if page contains breach-related content
        if self.is_breach_related(text_content):
            yield {
                'type': 'generic_darkweb',
                'source_url': response.url,
                'source_id': self.source_id,
                'content': text_content[:5000],
                'scraped_at': datetime.now().isoformat(),
                'page_title': response.css('title::text').get(),
            }
    
    def is_breach_related(self, text):
        """Check if text contains breach-related keywords"""
        keywords = [
            'breach', 'leak', 'dump', 'database', 'hack', 'hacked',
            'password', 'credentials', 'account', 'stolen', 'exposed'
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)


# Scrapy settings for all spiders
SCRAPY_SETTINGS = {
    'BOT_NAME': 'darkweb_scraper',
    'ROBOTSTXT_OBEY': False,
    'CONCURRENT_REQUESTS': 1,
    'DOWNLOAD_DELAY': 5,
    'COOKIES_ENABLED': False,
    'TELNETCONSOLE_ENABLED': False,
    'DEFAULT_REQUEST_HEADERS': {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en',
    },
    'DOWNLOADER_MIDDLEWARES': {
        'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 750,
    },
    'LOG_LEVEL': 'INFO',
}

