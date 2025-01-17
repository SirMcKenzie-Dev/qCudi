# scraper_project/scrapers/base_scraper.py
from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
import asyncio
import logging
import random  # Used in rate limiting
from typing import Callable, Optional, Tuple, List


ProgressCallback = Callable[[int, str, int, Optional[int]], None]


class BaseScraper(ABC):
    def __init__(self, driver: Optional[webdriver.Chrome] = None,
                 progress_callback: Optional[Callable] = None) -> None:
        """
        Initialize base scraper.

        Args:
            driver: Selenium WebDriver instance
            progress_callback: Function to report progress
        """
        self.driver = driver
        self.progress_callback = progress_callback

    async def authenticate(self, credentials: dict) -> bool:
        """Handle site-specific authentication"""
        pass

    async def rate_limit(self):
        """Implement rate limiting to avoid detection"""
        await asyncio.sleep(random.uniform(1.0, 3.0))

    @abstractmethod
    async def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate if URL is supported for this scraper"""
        pass

    @abstractmethod
    async def get_media_elements(self) -> list:
        """Get all media elements from the page"""
        pass

    @abstractmethod
    async def process_media_element(self, element, index: int, download_dir: str) -> tuple[bool, str]:
        await self.rate_limit()
        """Process a single media element"""
        pass

    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.driver:
                self.driver.quit()
        except Exception as e:
            logging.error(f"Error cleaning up: {e}")

    async def scroll_to_load(self):
        """Default scroll behavior - can be overridden by specific scrapers"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            await asyncio.sleep(2)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
