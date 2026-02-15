"""
Scrapers for Dark Web Monitoring
"""

# Lazy imports not needed here if spiders are imported only when needed
# But if we want to keep the __all__ we should keep imports but now safe due to dark_web_spider.py changes
from .dark_web_spider import BreachForumSpider, PastebinSpider, GenericDarkWebSpider

__all__ = ['BreachForumSpider', 'PastebinSpider', 'GenericDarkWebSpider']

