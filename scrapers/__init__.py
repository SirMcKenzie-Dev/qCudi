# scrapers/__init__.py
from .base_scraper import BaseScraper
from .fapello_scraper import FapelloScraper
from .instagram_scraper import InstagramScraper
# from .threads_scraper import ThreadsScraper  # Not implemented yet
from .scraper_controller import ScraperController

__all__ = ['BaseScraper', 'FapelloScraper', 'InstagramScraper', 'ScraperController']  # Add "ThreadScraper"
