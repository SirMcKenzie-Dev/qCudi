import os  # noqa
import time  # noqa
import httpx  # noqa
import logging
import asyncio
from typing import Tuple, List, Optional  # noqa
from selenium import webdriver  # noqa
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys  # noqa
from scrapers.base_scraper import BaseScraper
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class InstagramScraper(BaseScraper):
    """
    Enhanced Instagram scraper with improved error handling and consistency
    with the base scraper interface.
    """
    def __init__(self, driver=None, progress_callback=None):
        super().__init__(driver, progress_callback)
        self.main_window = None
        self.download_log = []
        self.is_authenticated = False

    async def validate_url(self, url: str) -> tuple[bool, str]:
        """
        Validates if the URL is a valid Instagram URL.

        Args:
            url (str): URL to validate

        Returns:
            tuple[bool, str]: (is_valid, error_message)
        """
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                return False, "Invalid URL format"

            if result.scheme not in ['http', 'https']:
                return False, "URL must use HTTP or HTTPS"

            if 'instagram.com' not in result.netloc.lower():
                return False, "Not a valid Instagram domain"

            # Validate path structure
            path_parts = result.path.strip('/').split('/')
            valid_paths = ['p', 'stories', 'reel', '']  # '' for profile URLs

            if path_parts[0] not in valid_paths:
                return False, "Invalid Instagram URL path"

            return True, "URL is valid"

        except Exception as e:
            return False, f"URL validation error: {str(e)}"

    async def get_media_elements(self) -> list:
        """Get all media elements from the current page"""
        await self.scroll_to_load()

        elements = self.driver.find_elements(
            By.CSS_SELECTOR,
            'article img[style*="object-fit: cover"]'
        )

        self.total_thumbnails = len(elements)
        if self.progress_callback:
            self.progress_callback(0, "", 0, self.total_thumbnails)

        return elements

    async def process_media_element(self, element, index: int, download_dir: str) -> tuple[bool, str]:
        """Process a single Instagram media element"""
        try:
            if not self.main_window:
                self.main_window = self.driver.current_window_handle

            # Click the post to open it in a modal
            element.click()
            await asyncio.sleep(1)

            # Wait for modal to appear
            modal = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="dialog"]'))
            )

            # Check for carousel
            carousel_buttons = modal.find_elements(By.CSS_SELECTOR, 'button[aria-label="Next"]')
            urls = []

            if carousel_buttons:
                # Handle carousel post
                while True:
                    try:
                        img = WebDriverWait(modal, 5).until(
                            EC.presence_of_element_located((
                                By.CSS_SELECTOR,
                                'img[style*="object-fit: contain"]'
                            ))
                        )
                        urls.append(img.get_attribute('src'))

                        next_button = modal.find_element(By.CSS_SELECTOR, 'button[aria-label="Next"]')
                        next_button.click()
                        await asyncio.sleep(0.5)
                    except (TimeoutException, NoSuchElementException):
                        break
            else:
                # Single image/video post
                try:
                    img = WebDriverWait(modal, 5).until(
                        EC.presence_of_element_located((
                            By.CSS_SELECTOR,
                            'img[style*="object-fit: contain"]'
                        ))
                    )
                    urls.append(img.get_attribute('src'))
                except TimeoutException:
                    # Check for video
                    try:
                        video = modal.find_element(By.TAG_NAME, 'video')
                        urls.append(video.get_attribute('src'))
                    except NoSuchElementException:
                        pass

            # Close modal
            close_button = modal.find_element(By.CSS_SELECTOR, 'button[aria-label="Close"]')
            close_button.click()
            await asyncio.sleep(0.5)

            # Download all found media
            success = False
            for idx, url in enumerate(urls):
                if url:
                    is_video = url.endswith('.mp4')
                    ext = '.mp4' if is_video else '.jpg'
                    filename = f"instagram_{index}_{idx}{ext}"
                    success = await self.download_image(url, filename, download_dir)

                    if success and self.progress_callback:
                        self.progress_callback(index + 1, url, 200, self.total_thumbnails)

            return success, urls[0] if urls else ""

        except Exception as e:
            logging.error(f"Error processing media {index}: {e}")
            if self.progress_callback:
                self.progress_callback(index + 1, "", 500, self.total_thumbnails)
            return False, str(e)

    async def scroll_to_load(self):
        """Scroll the page to load more content"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scrolls = 0
        max_scrolls = 10  # Prevent infinite scrolling

        while scrolls < max_scrolls:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            await asyncio.sleep(2)

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break

            last_height = new_height
            scrolls += 1
