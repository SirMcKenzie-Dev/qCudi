# scraper_project/scrapers/instagram_scraper.py
"""
Enhanced Instagram scraper module with improved error handling and DOM management.
This module provides a robust implementation for scraping media content from Instagram
while respecting rate limits and handling various media types (images, videos, carousels).

Version: 2024.01.20
"""

import logging
import asyncio
import re
import random
from typing import Tuple, List
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .base_scraper import BaseScraper
from .instagram_dom_map import InstagramDOMMap

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class InstagramScraper(BaseScraper):
    """
    Enhanced Instagram scraper with improved error handling and DOM management.

    Attributes:
        dom (InstagramDOMMap): Centralized DOM mapping instance
        main_window: Main browser window handle
        rate_limit_delay (float): Base delay between requests
        total_thumbnails (int): Total number of media items found

    Methods:
        validate_url: Validates Instagram URLs
        get_media_elements: Retrieves all media elements from the page
        process_media_element: Processes individual media elements
        scroll_to_load: Implements infinite scroll with rate limiting
    """
    def __init__(self, driver=None, progress_callback=None):
        super().__init__(driver, progress_callback)
        self.dom = InstagramDOMMap()
        self.main_window = None
        self.rate_limit_delay = 2.0
        self.total_thumbnails = 0
        logger.info(f"Instagram scraper initialized with DOM version: {self.dom.VERSION}")

    async def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        Validates Instagram URLs with improved pattern matching.

        Args:
            url: The URL to validate

        Returns:
            Tuple containing (is_valid, message)
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

            # Empty path (instagram.com) is valid
            if not path_parts[0]:
                return True, "URL is valid"

            # Valid path prefixes
            valid_paths = ['p', 'stories', 'reel']
            if path_parts[0] in valid_paths:
                return True, "URL is valid"

            # Username validation
            username = path_parts[0]
            if not re.match(r'^[A-Za-z0-9._]{1,30}$', username):
                return False, "Invalid Instagram username format"

            return True, "URL is valid"

        except Exception as e:
            logger.error(f"URL validation error: {str(e)}")
            return False, f"URL validation error: {str(e)}"

    async def authenticate(self, credentials: dict) -> bool:
        """Handle Instagram authentication with detailed logging"""
        try:
            if not credentials.get('username') or not credentials.get('password'):
                logger.error("Missing credentials")
                return False

            # Go to login page
            logger.debug("Navigating to Instagram login page")
            self.driver.get('https://www.instagram.com/accounts/login/')
            await asyncio.sleep(5)  # Wait for page load

            # Log current URL to verify we're on the right page
            current_url = self.driver.current_url
            logger.debug(f"Current URL after navigation: {current_url}")

            # Log page source for debugging (first 500 chars)
            page_source = self.driver.page_source[:500]
            logger.debug(f"Page source preview: {page_source}")

            try:
                # Wait for and find username field
                logger.debug("Waiting for username field")
                username_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "username"))
                )
                logger.debug("Username field found")

                # Find password field
                logger.debug("Looking for password field")
                password_input = self.driver.find_element(By.NAME, "password")
                logger.debug("Password field found")

                # Enter credentials
                logger.debug(f"Entering username: {credentials['username']}")
                username_input.clear()
                username_input.send_keys(credentials['username'])
                await asyncio.sleep(1)

                logger.debug("Entering password")
                password_input.clear()
                password_input.send_keys(credentials['password'])
                await asyncio.sleep(1)

                # Log form state
                form = self.driver.find_element(By.TAG_NAME, "form")
                logger.debug(f"Form found with action: {form.get_attribute('action')}")

                # Submit form
                logger.debug("Submitting login form")
                password_input.send_keys(Keys.RETURN)
                await asyncio.sleep(5)  # Wait for login process

                # Log current URL after submission
                after_submit_url = self.driver.current_url
                logger.debug(f"URL after form submission: {after_submit_url}")

                # Check for various post-login elements
                try:
                    # Multiple potential success indicators
                    success_selectors = [
                        "svg[aria-label='Home']",
                        "span[class='_aaav']",  # Profile link
                        "a[href='/direct/inbox/']",  # Messages link
                        "div[class='_aak6']"  # Main nav container
                    ]

                    for selector in success_selectors:
                        try:
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            )
                            logger.info(f"Login successful - found element: {selector}")
                            self.is_authenticated = True
                            return True
                        except TimeoutException:
                            continue

                    logger.error("Could not verify successful login - no success indicators found")
                    return False

                except Exception as e:
                    logger.error(f"Error checking login status: {str(e)}")
                    return False

            except NoSuchElementException as e:
                logger.error(f"Could not find login form element: {str(e)}")
                return False
            except TimeoutException as e:
                logger.error(f"Timeout waiting for login form: {str(e)}")
                return False

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}", exc_info=True)
            return False

    async def get_media_elements(self) -> List:
        """Enhanced media element detection with debugging"""
        try:
            await self.scroll_to_load()

            # Log the current URL
            current_url = self.driver.current_url
            logger.debug(f"Current URL: {current_url}")

            # Log the page source for debugging
            logger.debug("Page source preview: %s", self.driver.page_source[:500])

            # Try different selector strategies
            selectors_to_try = [
                (f"{self.dom.POST_GRID['post_link']} {self.dom.POST_GRID['thumbnail']}", "Default selector"),
                (self.dom.POST_GRID['profile_posts'], "Profile posts selector"),
                ("article img", "Simple img selector"),
                ("a[href*='/p/'] img", "Link-based img selector")
            ]

            elements = []
            for selector, desc in selectors_to_try:
                logger.debug(f"Trying selector: {selector} ({desc})")
                found_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                logger.debug(f"Found {len(found_elements)} elements with {desc}")

                if found_elements:
                    # Log details of first few elements
                    for i, elem in enumerate(found_elements[:3]):
                        try:
                            src = elem.get_attribute('src')
                            class_name = elem.get_attribute('class')
                            logger.debug(f"Element {i} - src: {src}, class: {class_name}")
                        except Exception as e:
                            logger.debug(f"Couldn't get attributes for element {i}: {e}")

                    elements = found_elements
                    logger.info(f"Successfully found {len(elements)} elements with {desc}")
                    break

            if not elements:
                logger.warning("No elements found with any selector strategy")

            self.total_thumbnails = len(elements)
            if self.progress_callback:
                self.progress_callback(0, "", 0, self.total_thumbnails)

            return elements

        except Exception as e:
            logger.error(f"Error in get_media_elements: {str(e)}", exc_info=True)
            return []

    async def process_media_element(self, element, index: int, download_dir: str) -> Tuple[bool, str]:
        """Simplified media processing focused on thumbnails"""
        try:
            # Try to get the image URL directly
            src = element.get_attribute('src')
            if not src:
                logger.debug(f"No src attribute found for element {index}")
                return False, "No source URL found"

            logger.info(f"Found image URL for element {index}: {src}")

            # Download the thumbnail directly
            filename = f"instagram_thumbnail_{index}.jpg"
            success = await self.download_image(src, filename, download_dir)

            if success:
                logger.info(f"Successfully downloaded thumbnail {index}")
                if self.progress_callback:
                    self.progress_callback(index + 1, src, 200, self.total_thumbnails)
            else:
                logger.error(f"Failed to download thumbnail {index}")

            return success, src

        except Exception as e:
            logger.error(f"Error processing element {index}: {str(e)}", exc_info=True)
            if self.progress_callback:
                self.progress_callback(index + 1, "", 500, self.total_thumbnails)
            return False, str(e)

        # """Process media elements with detailed logging"""
        # try:
        #     if not self.main_window:
        #         self.main_window = self.driver.current_window_handle

        #     # Get post link and log details
        #     post_link = element
        #     if element.tag_name == 'img':
        #         logger.debug("Element is an img tag, finding parent link")
        #         post_link = element.find_element(By.XPATH, './ancestor::a[@role="link"]')

        #     # Log post details
        #     post_url = post_link.get_attribute('href')
        #     logger.info(f"Processing post {index + 1}: {post_url}")

        #     # Log element attributes
        #     element_attrs = {}
        #     try:
        #         element_attrs = {
        #             'class': element.get_attribute('class'),
        #             'src': element.get_attribute('src'),
        #             'alt': element.get_attribute('alt')
        #         }
        #         logger.debug("Element attributes: %s", element_attrs)
        #     except Exception:
        #         logger.debug("Could not get all element attributes")

        #     # Click and log
        #     logger.debug("Clicking post link to open modal")
        #     post_link.click()
        #     await asyncio.sleep(self.rate_limit_delay)

        #     # Wait for and log modal
        #     logger.debug("Waiting for modal with selector: %s", self.dom.MODAL['dialog'])
        #     modal = WebDriverWait(self.driver, 10).until(
        #         EC.presence_of_element_located((
        #             By.CSS_SELECTOR,
        #             self.dom.MODAL['dialog']
        #         ))
        #     )
        #     logger.debug("Modal found, proceeding to extract media")

        #     # Extract and log media URLs
        #     media_urls = await self._extract_media_urls(modal)
        #     logger.info("Found %d media URLs in post", len(media_urls))
        #     for idx, url in enumerate(media_urls):
        #         logger.debug("Media URL %d: %s", idx + 1, url)

        #     # Close modal
        #     logger.debug("Closing modal")
        #     close_button = modal.find_element(
        #         By.CSS_SELECTOR,
        #         self.dom.MODAL['close']
        #     )
        #     close_button.click()
        #     await asyncio.sleep(self.rate_limit_delay)

        #     # Download media with logging
        #     success = False
        #     for idx, url in enumerate(media_urls):
        #         if url:
        #             ext = '.mp4' if url.endswith('.mp4') else '.jpg'
        #             filename = f"instagram_{index}_{idx}{ext}"
        #             logger.info(f"Downloading media {idx + 1} from URL: {url}")
        #             logger.debug(f"Saving as: {filename}")

        #             success = await self.download_image(url, filename, download_dir)
        #             logger.info(f"Download {'successful' if success else 'failed'}")

        #             if success and self.progress_callback:
        #                 self.progress_callback(
        #                     index + 1,
        #                     url,
        #                     200,
        #                     self.total_thumbnails
        #                 )

        #     return success, media_urls[0] if media_urls else ""

        # except Exception as e:
        #     logger.error(f"Error processing media {index}: {str(e)}", exc_info=True)
        #     if self.progress_callback:
        #         self.progress_callback(index + 1, "", 500, self.total_thumbnails)
        #     return False, str(e)

    async def scroll_to_load(self):
        """Improved scroll with debug logging"""
        try:
            # Wait for initial content
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "img"))
            )
            logger.debug("Initial content loaded")

            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scrolls = 0
            max_scrolls = 3  # Reduced for testing

            while scrolls < max_scrolls:
                logger.debug(f"Scroll attempt {scrolls + 1}/{max_scrolls}")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                await asyncio.sleep(2)

                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    logger.debug("No new content loaded after scroll")
                    break

                last_height = new_height
                scrolls += 1

                # Log any new images found after scroll
                images = self.driver.find_elements(By.TAG_NAME, "img")
                logger.debug(f"Found {len(images)} images after scroll {scrolls}")

        except Exception as e:
            logger.error(f"Error during scroll: {str(e)}", exc_info=True)

    async def _extract_media_urls(self, modal) -> List[str]:
        """Extract media URLs with debug information"""
        urls = []
        logger.debug("Starting media URL extraction from modal")

        try:
            # Check for carousel
            carousel_next = modal.find_elements(
                By.CSS_SELECTOR,
                self.dom.MODAL['carousel_next']
            )
            logger.debug("Carousel navigation %s", "found" if carousel_next else "not found")

            if carousel_next:
                logger.info("Processing carousel post")
                while True:
                    try:
                        # Try image first
                        try:
                            logger.debug("Looking for image with selector: %s", self.dom.MODAL['image'])

                            img = WebDriverWait(modal, 5).until(
                                EC.presence_of_element_located((
                                    By.CSS_SELECTOR,
                                    self.dom.MODAL['image']
                                ))
                            )
                            img_url = img.get_attribute('src')
                            logger.debug("Found image URL: %s", img_url)
                            urls.append(img_url)
                        except TimeoutException:
                            logger.debug("No image found, checking for video")
                            # Try video
                            video = modal.find_element(
                                By.CSS_SELECTOR,
                                self.dom.MODAL['video']
                            )
                            video_url = video.get_attribute('src')
                            logger.debug("Found video URL: %s", video_url)
                            urls.append(video_url)

                        # Move to next slide
                        logger.debug("Moving to next slide")
                        carousel_next[0].click()
                        await asyncio.sleep(self.rate_limit_delay)

                    except (TimeoutException, NoSuchElementException) as e:
                        logger.debug("No more slides found: %s", str(e))
                        break
            else:
                logger.info("Processing single media post")
                try:
                    logger.debug("Looking for single image")
                    img = WebDriverWait(modal, 5).until(
                        EC.presence_of_element_located((
                            By.CSS_SELECTOR,
                            self.dom.MODAL['image']
                        ))
                    )
                    img_url = img.get_attribute('src')
                    logger.debug("Found image URL: %s", img_url)
                    urls.append(img_url)
                except TimeoutException:
                    logger.debug("No image found, checking for video")
                    try:
                        video = modal.find_element(
                            By.CSS_SELECTOR,
                            self.dom.MODAL['video']
                        )
                        video_url = video.get_attribute('src')
                        logger.debug("Found video URL: %s", video_url)
                        urls.append(video_url)
                    except NoSuchElementException:
                        logger.warning("No media (image or video) found in post")

        except Exception as e:
            logger.error("Error extracting media URLs: %s", str(e), exc_info=True)

        logger.info("Extracted %d media URLs", len(urls))
        return urls

    async def rate_limit(self):
        """
        Improved rate limiting with jitter to avoid detection.
        Implements exponential backoff when encountering rate limits.
        """
        jitter = random.uniform(0.5, 1.5)
        await asyncio.sleep(self.rate_limit_delay * jitter)
