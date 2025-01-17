# scraper_project/scrapers/scraper_controller.py
import os
import time
import shutil
import logging
import httpx
from typing import Dict, Type, Optional, Tuple
from selenium import webdriver
from .base_scraper import BaseScraper
from .fapello_scraper import FapelloScraper
from .instagram_scraper import InstagramScraper
from config.config import ScraperConfig
from utils.browser_setup import BrowserSetup
from selenium.common.exceptions import WebDriverException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScraperController:
    """
    Controller class that manages different scrapers and coordinates the scraping process.
    Handles scraper selection, browser management, and overall process coordination.

    Attributes:
        config (ScraperConfig): Configuration object
        progress_callback (callable): Callback function for progress updates
        driver (webdriver.Chrome): Selenium WebDriver instance
        scraper (BaseScraper): Current active scraper instance
    """

    SCRAPER_MAP = {
        "fapello.com": FapelloScraper,
        "instagram.com": InstagramScraper,
        "threads.net": None  # Missing implementation
    }

    def __init__(self, progress_callback=None, config_file="config.json"):
        """
        Initialize the scraper controller.

        Args:
            progress_callback (callable, optional): Function to report progress
            config_file (str): Path to configuration file
        """
        self.start_time = time.time()
        self.config = ScraperConfig.load_config(config_file)
        self.progress_callback = progress_callback
        self.driver = None
        self.scraper = None

    def get_scraper_for_url(self, url: str) -> Optional[Type[BaseScraper]]:
        """
        Determine appropriate scraper class based on URL.

        Args:
            url (str): URL to be scraped

        Returns:
            Optional[Type[BaseScraper]]: Appropriate scraper class or None if not supported
        """
        for domain, scraper_class in self.SCRAPER_MAP.items():
            if domain in url.lower():
                return scraper_class
        return None

    async def check_disk_space(self, required_mb=500):
        """
        Check if there's sufficient disk space available.

        Args:
            required_mb (int): Required space in megabytes

        Raises:
            RuntimeError: If insufficient disk space
        """
        total, used, free = shutil.disk_usage(self.config.download_directory)
        free_mb = free // (1024 * 1024)

        if free_mb < required_mb:
            raise RuntimeError(
                f"Insufficient disk space. Required: {required_mb}MB, Available: {free_mb}MB"
            )

    async def run(self, url: str) -> tuple[int, int]:
        """
        Main method to run the scraping process.

        Args:
            url (str): URL to scrape

        Returns:
            tuple[int, int]: (successful_downloads, total_items)

        Raises:
            ValueError: If URL is invalid or unsupported
            RuntimeError: If scraping fails
        """
        try:
            # Initialize scraper
            scraper_class = self.get_scraper_for_url(url)
            if not scraper_class:
                raise ValueError(f"Unsupported website. Supported: {', '.join(self.SCRAPER_MAP.keys())}")

            # Create download directory
            os.makedirs(self.config.download_directory, exist_ok=True)

            # Check disk space
            await self.check_disk_space()

            # Initialize browser and scraper
            self.driver = BrowserSetup.create_driver(self.config.chrome_driver_path)
            self.scraper = scraper_class(self.driver, self.progress_callback)

            # Validate URL
            is_valid, error_message = await self.scraper.validate_url(url)
            if not is_valid:
                raise ValueError(error_message)

            # Start scraping process
            self.driver.get(url)
            media_elements = await self.scraper.get_media_elements()
            total_elements = len(media_elements)
            successful_downloads = 0

            # Signal total count if callback exists
            if self.progress_callback:
                self.progress_callback(0, "", 0, total_elements)

            # Process each media element
            for index, element in enumerate(media_elements):
                success, message = await self.scraper.process_media_element(
                    element, index, self.config.download_directory
                )
                if success:
                    successful_downloads += 1

            return successful_downloads, total_elements

        except webdriver.WebDriverException as e:
            raise RuntimeError(f"Browser error: {str(e)}")
        except httpx.HTTPError as e:
            raise RuntimeError(f"Network error: {str(e)}")
        except Exception as e:
            logging.error(f"Scraping failed: {e}")
            raise RuntimeError(f"Scraping failed: {e}") from e

        finally:
            if self.driver:
                self.driver.quit()

            self.end_time = time.time()
            duration = self.end_time - self.start_time
            logger.info(f"Total execution time: {duration:.2f} seconds")
