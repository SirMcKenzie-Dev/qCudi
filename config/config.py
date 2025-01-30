# scraper_project/config/config.py
import os
import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScraperConfig:
    """Configuration class for the scraper application."""
    chrome_driver_path: str
    download_directory: str
    supported_domains: List[str]
    min_image_width: int
    min_image_height: int
    scroll_wait_time: int
    download_timeout: int
    max_retries: int
    selectors: Dict[str, Dict[str, str]]
    credentials: Dict[str, Dict[str, str]] = field(default_factory=dict)

    @classmethod
    def load_config(cls, config_file: str = "config.json") -> 'ScraperConfig':
        """
        Load configuration from file or use defaults.

        Args:
            config_file (str): Path to configuration file

        Returns:
            ScraperConfig: Configuration instance
        """
        default_config = {
            "chrome_driver_path": "/usr/local/bin/chromedriver",
            "download_directory": os.path.join(os.getcwd(), "scraped_media"),
            "min_image_width": 300,
            "min_image_height": 300,
            "scroll_wait_time": 2,
            "download_timeout": 30,
            "max_retries": 3,
            "supported_domains": [
                "fapello.com",
                "instagram.com",
                "threads.net"
            ],
            "selectors": {
                "fapello": {
                    "thumbnails": "img.w-full.h-full.absolute.object-cover.inset-0",
                    "full_image": "img"
                },
                "instagram": {
                    "thumbnails": "article img",
                    "full_image": "div._aagv img"
                }
            },
            "credentials": {}  # Empty by default
        }

        try:
            # Load from file if exists
            if os.path.exists(config_file):
                logger.debug(f"Loading config from file: {config_file}")
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                    default_config.update(file_config)
            else:
                logger.warning(f"Config file not found: {config_file}, using defaults")

            # Load credentials from environment if not in file
            if not default_config.get("credentials", {}).get("instagram.com"):
                username = os.getenv("INSTAGRAM_USERNAME")
                password = os.getenv("INSTAGRAM_PASSWORD")
                if username and password:
                    logger.debug("Loading Instagram credentials from environment")
                    if "credentials" not in default_config:
                        default_config["credentials"] = {}
                    default_config["credentials"]["instagram.com"] = {
                        "username": username,
                        "password": password
                    }

            return cls(**default_config)

        except Exception as e:
            logger.error(f"Error loading config: {e}. Using defaults.")
            return cls(**default_config)

    def save_config(self, config_file: str = "config.json"):
        """
        Save configuration to file.

        Args:
            config_file (str): Path to save configuration
        """
        try:
            config_data = {
                field: getattr(self, field)
                for field in self.__dataclass_fields__
                if field != 'credentials'  # Don't save credentials to file
            }
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=4)
            logger.info(f"Configuration saved to {config_file}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def get_credentials(self, domain: str) -> Optional[Dict[str, str]]:
        """
        Get credentials for a specific domain.

        Args:
            domain (str): Domain to get credentials for

        Returns:
            Optional[Dict[str, str]]: Credentials if found, None otherwise
        """
        return self.credentials.get(domain)
