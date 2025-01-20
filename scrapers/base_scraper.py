# scraper_project/scrapers/base_scraper.py
from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.options import Options  # noqa
from selenium.webdriver.common.by import By # noqa
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException # noqa
import asyncio
import logging
import os
import httpx
import random  # Used for rate limiting
from typing import Callable, Optional, Tuple, List # noqa


ProgressCallback = Callable[[int, str, int, Optional[int]], None]


class BaseScraper(ABC):
    def __init__(self, driver: Optional[webdriver.Chrome] = None,
                 progress_callback: Optional[ProgressCallback] = None) -> None:
        self.driver = driver
        self.progress_callback = progress_callback
        self.total_thumbnails = 0  # Add this to track total items

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

    async def download_image(self, url: str, filename: str, download_dir: str, max_retries: int = 3) -> bool:
        """
        Common download method for all scrapers
        """
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(url)
                    response.raise_for_status()

                    file_path = os.path.join(download_dir, filename)
                    with open(file_path, 'wb') as f:
                        f.write(response.content)

                    logging.info(f"Downloaded: {file_path}")
                    return True

            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt == max_retries - 1:
                    return False
                await asyncio.sleep(2 ** attempt)
