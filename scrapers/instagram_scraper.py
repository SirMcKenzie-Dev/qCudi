# scraper_project/scrapers/instagram_scraper.py
import os
import logging
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_scraper import BaseScraper
from selenium.common.exceptions import TimeoutException
from typing import List, Tuple, Optional


class InstagramScraper(BaseScraper):
    def __init__(self, driver=None, progress_callback=None):
        super().__init__(driver, progress_callback)
        self.main_window = None
        self.download_log = []

    async def process_media_element(self, element, index: int, download_dir: str) -> tuple[bool, str]:
        """
        Process Instagram media elements using similar logic to FapelloScraper
        """
        try:
            # Use similar logic to FapelloScraper but with Instagram-specific selectors
            parent = element.find_element(By.XPATH, "./ancestor::a")
            intermediate_url = parent.get_attribute('href')

            if not intermediate_url:
                return False, "No link found"

            self.driver.execute_script(f"window.open('{intermediate_url}', '_blank');")
            self.driver.switch_to.window(self.driver.window_handles[-1])

            # Wait for Instagram image to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div._aagv img"))
            )

            # Get full resolution image
            full_res_element = self.driver.find_element(By.CSS_SELECTOR, "div._aagv img")
            full_res_url = full_res_element.get_attribute('src')

            if not full_res_url:
                self.driver.close()
                self.driver.switch_to.window(self.main_window)
                return False, "No source URL found"

            # Download image using same method as FapelloScraper
            filename = f"instagram_{index + 1}{os.path.splitext(full_res_url.split('?')[0])[1]}"
            success = await self.download_image(full_res_url, filename, download_dir)

            self.driver.close()
            self.driver.switch_to.window(self.main_window)

            if success:
                if self.progress_callback:
                    self.progress_callback(index + 1, full_res_url, 200)
                return True, full_res_url
            else:
                if self.progress_callback:
                    self.progress_callback(index + 1, full_res_url, 500)
                return False, "Download failed"

        except Exception as e:
            logging.error(f"Error processing Instagram media {index}: {e}")
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.main_window)
            return False, str(e)
