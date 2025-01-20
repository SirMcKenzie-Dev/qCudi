# scraper_project/scrapers/scraper_controller.py
"""
Controller class for managing different website scrapers.
Handles initialization, authentication, and coordinates the scraping process.
"""

import os
import time
import httpx
import shutil
import asyncio
import logging
from .base_scraper import BaseScraper
from config.config import ScraperConfig
from typing import Dict, Type, Optional
from .fapello_scraper import FapelloScraper
from utils.browser_setup import BrowserSetup
from .instagram_scraper import InstagramScraper
from selenium.common.exceptions import WebDriverException

logger = logging.getLogger(__name__)


class ScraperController:
    """Controller class that manages different scrapers and coordinates the scraping process."""

    SCRAPER_MAP = {
        "fapello.com": FapelloScraper,
        "instagram.com": InstagramScraper,
        "threads.net": None  # Not implemented
    }

    def __init__(self, progress_callback=None, config_file="config.json"):
        """Initialize controller with progress callback and config."""
        self.start_time = time.time()
        self.config = ScraperConfig.load_config(config_file)
        self.progress_callback = progress_callback
        self.driver = None
        self.scraper = None
        logger.debug("ScraperController initialized with config file: %s", config_file)

    def get_scraper_for_url(self, url: str) -> Optional[Type[BaseScraper]]:
        """Determine appropriate scraper class based on URL."""
        for domain, scraper_class in self.SCRAPER_MAP.items():
            if domain in url.lower():
                logger.debug("Found matching scraper for domain: %s", domain)
                return scraper_class
        logger.warning("No matching scraper found for URL: %s", url)
        return None

    async def check_disk_space(self, required_mb=500):
        """Check if there's sufficient disk space available."""
        total, used, free = shutil.disk_usage(self.config.download_directory)
        free_mb = free // (1024 * 1024)
        logger.debug("Disk space check - Required: %dMB, Available: %dMB", required_mb, free_mb)

        if free_mb < required_mb:
            logger.error("Insufficient disk space - Required: %dMB, Available: %dMB", required_mb, free_mb)
            raise RuntimeError(
                f"Insufficient disk space. Required: {required_mb}MB, Available: {free_mb}MB"
            )

    def get_credentials(self, domain: str) -> Dict[str, str]:
        """Get credentials for a specific domain."""
        try:
            # Try config file first
            if hasattr(self.config, 'credentials') and domain in self.config.credentials:
                logger.debug("Found credentials in config file for domain: %s", domain)
                return self.config.credentials[domain]

            # Try environment variables
            if domain == "instagram.com":
                username = os.getenv('INSTAGRAM_USERNAME')
                password = os.getenv('INSTAGRAM_PASSWORD')

                if username and password:
                    logger.debug("Found Instagram credentials in environment variables")
                    return {'username': username, 'password': password}

                logger.warning("No credentials found for %s in config or environment", domain)
            return {}

        except Exception as e:
            logger.error("Error getting credentials: %s", str(e))
            return {}

    async def run(self, url: str) -> tuple[int, int]:
        """Main method to run the scraping process."""
        try:
            # Initialize scraper
            scraper_class = self.get_scraper_for_url(url)
            if not scraper_class:
                raise ValueError(f"Unsupported website. Supported: {', '.join(self.SCRAPER_MAP.keys())}")

            # Create download directory
            os.makedirs(self.config.download_directory, exist_ok=True)
            logger.debug("Download directory created: %s", self.config.download_directory)

            # Check disk space
            await self.check_disk_space()

            # Initialize browser and scraper
            logger.debug("Initializing browser and scraper")
            self.driver = BrowserSetup.create_driver(self.config.chrome_driver_path)
            self.scraper = scraper_class(self.driver, self.progress_callback)

            # Handle authentication if needed
            if isinstance(self.scraper, InstagramScraper):
                domain = "instagram.com"
                credentials = self.get_credentials(domain)

                if not credentials or not credentials.get('username') or not credentials.get('password'):
                    logger.error("Instagram credentials not found or incomplete")
                    raise RuntimeError("Instagram credentials not configured")

                username = credentials['username']
                logger.info("Attempting authentication for %s with username: %s", domain, username)

                auth_success = await self.scraper.authenticate(credentials)
                if not auth_success:
                    logger.error("Authentication failed for username: %s", username)
                    raise RuntimeError(f"{domain} authentication failed")

                logger.info("Successfully authenticated with %s as %s", domain, username)

            # Validate URL
            logger.debug("Validating URL: %s", url)
            is_valid, error_message = await self.scraper.validate_url(url)
            if not is_valid:
                raise ValueError(error_message)

            # Start scraping process
            logger.info("Starting scrape of URL: %s", url)
            self.driver.get(url)
            await asyncio.sleep(5)  # Wait for page load

            media_elements = await self.scraper.get_media_elements()
            total_elements = len(media_elements)
            logger.info("Found %d media elements to process", total_elements)

            successful_downloads = 0

            # Process each media element
            for index, element in enumerate(media_elements):
                logger.debug("Processing element %d of %d", index + 1, total_elements)
                success, message = await self.scraper.process_media_element(
                    element, index, self.config.download_directory
                )
                if success:
                    successful_downloads += 1
                    logger.debug("Successfully processed element %d", index + 1)
                else:
                    logger.warning("Failed to process element %d: %s", index + 1, message)

            logger.info("Completed scraping. Success rate: %d/%d", successful_downloads, total_elements)
            return successful_downloads, total_elements

        except WebDriverException as e:
            logger.error("Browser error: %s", str(e))
            raise RuntimeError(f"Browser error: {str(e)}")
        except httpx.HTTPError as e:
            logger.error("Network error: %s", str(e))
            raise RuntimeError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error("Scraping failed: %s", str(e), exc_info=True)
            raise
        finally:
            if self.driver:
                self.driver.quit()
                logger.debug("Browser driver closed")

            self.end_time = time.time()
            duration = self.end_time - self.start_time
            logger.info("Total execution time: %.2f seconds", duration)
