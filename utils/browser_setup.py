# scraper_project/utils/browser_setup.py
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

logger = logging.getLogger(__name__)


class BrowserSetup:
    """
    Utility class for configuring and creating Selenium WebDriver instances.
    Handles browser configuration and provides a consistent setup across different scrapers.

    Methods:
        configure_chrome_options(): Sets up Chrome options for headless browsing
        create_driver(): Creates and returns a configured Chrome WebDriver instance
    """

    @staticmethod
    def configure_chrome_options() -> Options:
        """
        Configures Chrome options for headless browsing.

        Returns:
            Options: Configured Chrome options object
        """
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-notifications')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        return options

    @staticmethod
    def create_driver(chrome_driver_path: str = '/usr/local/bin/chromedriver') -> webdriver.Chrome:
        """
        Creates and returns a configured Chrome WebDriver instance.

        Args:
            chrome_driver_path (str): Path to ChromeDriver executable

        Returns:
            webdriver.Chrome: Configured Chrome WebDriver instance

        Raises:
            Exception: If WebDriver initialization fails
        """
        try:
            service = Service(chrome_driver_path)
            options = BrowserSetup.configure_chrome_options()
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("Chrome WebDriver initialized successfully")
            return driver
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise
