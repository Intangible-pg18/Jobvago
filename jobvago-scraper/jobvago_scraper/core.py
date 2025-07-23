from abc import ABC, abstractmethod
from typing import List
from playwright.async_api import Page
from .models import JobItem

class ScraperStrategy(ABC):
    """
    Abstract Base Class (Interface) for all scraper strategies.
    This defines the 'contract' that every scraper must follow.
    """

    def __init__(self, site_name: str):
        self.site_name = site_name

    @abstractmethod
    async def scrape(self, page: Page) -> List[JobItem]:
        """
        The main method to perform scraping on a given Playwright page.

        Args:
            page: A Playwright Page object that has navigated to the target URL.

        Returns:
            A list of JobItem objects, each representing a scraped job posting.
            Returns an empty list if no jobs are found.
        """
        pass
