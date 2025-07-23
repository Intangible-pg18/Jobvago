from abc import ABC, abstractmethod
from typing import AsyncGenerator
from playwright.async_api import Browser

from .models import JobItem

class ScraperStrategy(ABC):
    """
    Defines the contract for a self-sufficient scraper.
    Each scraper is responsible for its own pagination logic.
    """

    def __init__(self, site_name: str):
        self.site_name = site_name

    @abstractmethod
    async def discover_jobs(self, browser: Browser) -> AsyncGenerator[JobItem, None]:
        """
        An async generator that discovers and yields JobItem objects.

        Args:
            browser: A Playwright Browser instance that the scraper can use
                     to create its own pages.

        Yields:
            JobItem: A new job posting as it is discovered.
        """
        yield