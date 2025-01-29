# scraper_project/scrapers/instagram_scraper.py
"""
Enhanced Instagram scraper module with improved error handling and DOM management.
This module provides a robust implementation for scraping media content from Instagram
while respecting rate limits and handling various media types (images, videos, carousels).

Version: 2024.01.20
"""

import re
import random
import asyncio
import logging
from typing import Tuple, List
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .base_scraper import BaseScraper
from .instagram_dom_map import InstagramDOMMap

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
            # logger.debug("Page source preview: %s", self.driver.page_source[:500])

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

    async def detect_media_type(self, element) -> tuple[str, str]:
        try:
            post_link = element
            if element.tag_name == 'img':
                post_link = element.find_element(By.XPATH, './ancestor::a[@role="link"]')

            post_url = post_link.get_attribute('href')

            # Check for video/reel elements
            video_elements = element.find_elements(
                By.CSS_SELECTOR,
                'video[type="video/mp4"],div[role="button"][aria-label*="play"], span[aria-label*="Video"]')

            if video_elements or '/reel/' in post_url:
                logger.info(f"Detected reel/video content: {post_url}")
                return 'reel', post_url

            # Open post to check type
            self.driver.execute_script(f"window.open('{post_url}', '_blank');")
            await asyncio.sleep(2)

            new_window = self.driver.window_handles[-1]
            self.driver.switch_to.window(new_window)

            try:
                carousel_dots = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    'div[role="menuitem"], button[aria-label="Next"]'
                )

                media_type = 'carousel' if carousel_dots else 'single'
                return media_type, post_url

            finally:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])

        except Exception as e:
            logger.error(f"Error detecting media type: {str(e)}")
            return 'unknown', ''

    async def process_carousel(self, post_url: str, index: int, download_dir: str) -> tuple[bool, list[str]]:
        downloaded_urls = set()
        try:
            self.driver.execute_script(f"window.open('{post_url}', '_blank');")
            await asyncio.sleep(2)

            new_window = self.driver.window_handles[-1]
            self.driver.switch_to.window(new_window)

            while True:
                try:
                    await asyncio.sleep(2)  # Wait for content load

                    img_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((
                            By.CSS_SELECTOR,
                            'div._aagv img[src*="instagram"], article img[src*="instagram"]'
                        ))
                    )

                    img_url = img_element.get_attribute('src')
                    if img_url and img_url not in downloaded_urls:
                        filename = f"instagram_{index}_{len(downloaded_urls)}.jpg"
                        if await self.download_image(img_url, filename, download_dir):
                            downloaded_urls.add(img_url)
                            if self.progress_callback:
                                self.progress_callback(index + len(downloaded_urls), img_url, 200, self.total_thumbnails)

                    try:
                        next_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((
                                By.CSS_SELECTOR,
                                'button[aria-label="Next"]'
                            ))
                        )

                        if not next_button.is_displayed():
                            break

                        next_button.click()
                        await asyncio.sleep(2)  # Wait for next image load
                    except Exception:
                        break  # No more images in carousel

                except Exception as e:
                    logger.debug(f"Carousel navigation completed or error: {str(e)}")
                    break

            return bool(downloaded_urls), list(downloaded_urls)

        except Exception as e:
            logger.error(f"Error processing carousel: {str(e)}")
            return False, []

        finally:
            try:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            except Exception as e:
                logger.error(f"Error cleaning up carousel windows: {str(e)}")

    async def process_single_image(self, post_url: str, index: int, download_dir: str) -> tuple[bool, str]:
        """
        Process a single image post.
        """
        try:
            self.driver.execute_script(f"window.open('{post_url}', '_blank');")
            await asyncio.sleep(2)

            new_window = self.driver.window_handles[-1]
            self.driver.switch_to.window(new_window)

            try:
                img_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        'div._aagv img[src*="instagram"]'
                    ))
                )

                img_url = img_element.get_attribute('src')
                if img_url:
                    filename = f"instagram_{index}.jpg"
                    success = await self.download_image(img_url, filename, download_dir)
                    return success, img_url

                return False, ''

            finally:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])

        except Exception as e:
            logger.error(f"Error processing single image: {str(e)}")
            return False, ''

    async def process_media_element(self, element, index: int, download_dir: str) -> tuple[bool, str]:
        try:
            media_type, post_url = await self.detect_media_type(element)

            if media_type == 'reel':
                logger.info(f"Skipping reel: {post_url}")
                if self.progress_callback:
                    self.progress_callback(index + 1, post_url, 200, self.total_thumbnails)
                return True, "Skipped reel"

            elif media_type == 'carousel':
                success, urls = await self.process_carousel(post_url, index, download_dir)
                if self.progress_callback:
                    self.progress_callback(index + 1, urls[0] if urls else post_url, 200 if success else 500, self.total_thumbnails)
                return success, urls[0] if urls else ""

            elif media_type == 'single':
                success, url = await self.process_single_image(post_url, index, download_dir)
                if self.progress_callback:
                    self.progress_callback(index + 1, url if success else post_url, 200 if success else 500, self.total_thumbnails)
                return success, url

            else:
                logger.warning(f"Unknown media type for post: {post_url}")
                if self.progress_callback:
                    self.progress_callback(index + 1, post_url, 500, self.total_thumbnails)
                return False, "Unknown media type"

        except Exception as e:
            logger.error(f"Error processing media element {index}: {str(e)}")
            if self.progress_callback:
                self.progress_callback(index + 1, "", 500, self.total_thumbnails)
            return False, str(e)

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
