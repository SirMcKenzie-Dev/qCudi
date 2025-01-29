# scraper_project/scrapers/fapello_scraper.py
import os
import httpx
import asyncio
import logging
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from scrapers.base_scraper import BaseScraper
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class FapelloScraper(BaseScraper):
    """
    Scraper implementation specific to Fapello website.
    Inherits from BaseScraper and implements website-specific scraping logic.

    Attributes:
        driver (webdriver.Chrome): Selenium WebDriver instance
        main_window: Main browser window handle
        download_log (list): Log of download attempts
        progress_callback (callable): Callback function for progress updates
    """

    def __init__(self, driver=None, progress_callback=None):
        super().__init__(driver)
        self.main_window = None
        self.download_log = []
        self.progress_callback = progress_callback

    async def validate_url(self, url: str) -> tuple[bool, str]:
        """
        Validates if the URL is a valid Fapello URL.

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

            if 'fapello.com' not in result.netloc.lower():
                return False, "Not a valid Fapello domain"

            return True, "URL is valid"
        except Exception as e:
            return False, f"URL validation error: {str(e)}"

    async def get_media_elements(self) -> list:
        """
        Retrieves all media elements from the current page.

        Returns:
            list: List of selenium WebElements representing thumbnails
        """
        await self.scroll_to_load()
        return self.driver.find_elements(
            By.CSS_SELECTOR,
            "img.w-full.h-full.absolute.object-cover.inset-0"
        )

    async def download_image(self, url: str, filename: str, download_dir: str, max_retries: int = 3) -> bool:
        """
        Downloads an image with retry mechanism.

        Args:
            url (str): URL of the image to download
            filename (str): Desired filename for downloaded image
            download_dir (str): Directory to save the image
            max_retries (int): Maximum number of retry attempts

        Returns:
            bool: True if download successful, False otherwise
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

    async def process_media_element(self, thumbnail, index: int, download_dir: str) -> tuple[bool, str]:
        try:
            if not self.main_window:
                self.main_window = self.driver.current_window_handle

            parent = thumbnail.find_element(By.XPATH, "./ancestor::a")
            intermediate_url = parent.get_attribute('href')
            if not intermediate_url:
                if self.progress_callback:
                    self.progress_callback(index + 1, "", 404, self.total_thumbnails)
                logging.warning(f"No link for thumbnail {index}")
                return False, "No link found"

            self.driver.execute_script(f"window.open('{intermediate_url}', '_blank');")
            await asyncio.sleep(1)

            new_window = None
            for handle in self.driver.window_handles:
                if handle != self.main_window:
                    new_window = handle
                    break

            if not new_window:
                if self.progress_callback:
                    self.progress_callback(index + 1, "", 500, self.total_thumbnails)
                return False, "Could not open new window"

            self.driver.switch_to.window(new_window)

            WebDriverWait(self.driver, 15).until(
                EC.presence_of_all_elements_located((By.TAG_NAME, "img"))
            )

            images = self.driver.find_elements(By.TAG_NAME, "img")
            largest_image = None
            max_area = 0

            excluded_keywords = ['thumbnail', 'banner', 'favicon', 'logo', 'icon', 'placeholder']

            for img in images:
                try:
                    src = img.get_attribute("src") or ""
                    img_class = img.get_attribute("class") or ""
                    img_id = img.get_attribute("id") or ""
                    combined_attributes = f"{src} {img_class} {img_id}".lower()

                    if any(keyword in combined_attributes for keyword in excluded_keywords):
                        continue

                    width = int(img.get_attribute("width") or 0)
                    height = int(img.get_attribute("height") or 0)
                    area = width * height

                    if width < 300 or height < 300:
                        continue

                    if area > max_area:
                        max_area = area
                        largest_image = img
                except (ValueError, TypeError):
                    continue

            if not largest_image:
                current_handle = self.driver.current_window_handle
                self.driver.switch_to.window(current_handle)
                self.driver.close()
                self.driver.switch_to.window(self.main_window)
                if self.progress_callback:
                    self.progress_callback(index + 1, "", 404, self.total_thumbnails)
                return False, "No suitable image found"

            full_res_url = largest_image.get_attribute('src')
            if not full_res_url:
                current_handle = self.driver.current_window_handle
                self.driver.switch_to.window(current_handle)
                self.driver.close()
                self.driver.switch_to.window(self.main_window)
                if self.progress_callback:
                    self.progress_callback(index + 1, "", 404, self.total_thumbnails)
                return False, "No source URL found"

            filename = f"image_{index + 1}{os.path.splitext(full_res_url.split('?')[0])[1]}"
            success = await self.download_image(full_res_url, filename, download_dir)

            current_handle = self.driver.current_window_handle
            self.driver.switch_to.window(current_handle)
            self.driver.close()
            self.driver.switch_to.window(self.main_window)

            if success:
                if self.progress_callback:
                    self.progress_callback(index + 1, full_res_url, 200, self.total_thumbnails)
                return True, full_res_url
            else:
                if self.progress_callback:
                    self.progress_callback(index + 1, full_res_url, 500, self.total_thumbnails)
                return False, "Download failed"

        except Exception as e:
            logging.error(f"Error processing thumbnail {index}: {e}")
            try:
                if self.main_window and self.main_window in self.driver.window_handles:
                    self.driver.switch_to.window(self.main_window)
                original_handle = self.driver.current_window_handle
                for handle in self.driver.window_handles:
                    if handle != original_handle:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                self.driver.switch_to.window(original_handle)
            except Exception as cleanup_error:
                logging.error(f"Error during cleanup: {cleanup_error}")

            if self.progress_callback:
                self.progress_callback(index + 1, "", 500, self.total_thumbnails)
            return False, str(e)
