# instagram_dom_map.py
"""
Instagram DOM mapping module providing centralized selectors for web scraping.
Includes comprehensive mapping of Instagram's web interface elements and helper methods
for selector retrieval.

Version: 2024.01.20
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class InstagramDOMMap:
    """
    Centralized DOM mapping for Instagram's web interface.
    Provides a single source of truth for all selectors with
    versioning and helper methods for selector retrieval.

    Attributes:
        VERSION (str): Current version of the DOM mapping
        POST_GRID (Dict): Selectors for the main post grid elements
        MODAL (Dict): Selectors for modal/lightbox elements
        STATUS (Dict): Selectors for status and error elements
    """
    VERSION: str = "2024.01.20"

    # Main post grid selectors - multiple options to try
    POST_GRID: Dict[str, str] = field(default_factory=lambda: {
        'article': 'article',  # Broader match
        'post_link': 'a[href*="/p/"]',  # Simpler link selector
        'thumbnail': 'img',  # We'll filter by attributes in code
        'post_container': 'div._aagv, div[class*="post-container"]',  # Multiple class options
        # Additional selectors for thumbnails
        'alt_thumbnail': 'img[crossorigin="anonymous"]',
        'profile_posts': 'article img[src*="instagram"]'
    })

    # Modal/lightbox selectors
    MODAL: Dict[str, str] = field(default_factory=lambda: {
        'dialog': 'div[role="dialog"]',
        'media_container': 'div._aagv',
        'image': 'img[style*="object-fit: contain"]',
        'video': 'video[type="video/mp4"]',
        'carousel_next': 'button[aria-label="Next"]',
        'carousel_prev': 'button[aria-label="Previous"]',
        'close': 'button[aria-label="Close"]',
    })

    # Error and status selectors
    STATUS: Dict[str, str] = field(default_factory=lambda: {
        'rate_limit': 'div[data-visualcompletion="error-state"]',
        'not_found': 'div[data-visualcompletion="empty-state"]',
        'loading': 'div._aanf'
    })

    @classmethod
    def get_version(cls) -> str:
        """
        Returns the current version of the DOM map.

        Returns:
            str: Version string in format YYYY.MM.DD
        """
        return cls.VERSION

    @classmethod
    def get_selector(cls, category: str, name: str) -> str:
        """
        Safely retrieves a selector by category and name.

        Args:
            category (str): Category of selector (POST_GRID, MODAL, or STATUS)
            name (str): Name of the specific selector

        Returns:
            str: The selector string if found, empty string if not found

        Example:
            >>> dom = InstagramDOMMap()
            >>> dom.get_selector('POST_GRID', 'thumbnail')
            'img'
        """
        return getattr(cls, category, {}).get(name, '')

    def verify_selector(self, category: str, name: str) -> bool:
        """
        Verifies if a selector exists in the specified category.

        Args:
            category (str): Category to check
            name (str): Selector name to verify

        Returns:
            bool: True if selector exists, False otherwise
        """
        return bool(self.get_selector(category, name))

    def list_selectors(self, category: str = None) -> Dict[str, Dict[str, str]]:
        """
        Lists all available selectors, optionally filtered by category.

        Args:
            category (str, optional): Category to filter by. Defaults to None.

        Returns:
            Dict: Dictionary of selectors, grouped by category
        """
        if category:
            return {category: getattr(self, category, {})}
        return {
            'POST_GRID': self.POST_GRID,
            'MODAL': self.MODAL,
            'STATUS': self.STATUS
        }
