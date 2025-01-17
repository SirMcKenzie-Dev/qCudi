# scraper_project/config/config.py
import os
import json
from typing import List
from dataclasses import dataclass


@dataclass
class ScraperConfig:
    chrome_driver_path: str
    download_directory: str
    supported_domains: List[str]
    min_image_width: int
    min_image_height: int
    scroll_wait_time: int
    download_timeout: int
    max_retries: int
    selectors: dict  # Add website-specific selectors

    @classmethod
    def load_config(cls, config_file: str = "config.json"):
        base_path = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_path, config_file)

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
            }
        }
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    default_config.update(config_data)
            return cls(**default_config)
        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")
            return cls(**default_config)

    def save_config(self, config_file: str = "config.json"):
        config_data = {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=4)
