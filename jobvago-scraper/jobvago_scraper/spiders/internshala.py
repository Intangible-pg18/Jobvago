import asyncio
from typing import List
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from pydantic import ValidationError

from jobvago_scraper.core import ScraperStrategy
from jobvago_scraper.models import JobItem

class InternshalaScraper(ScraperStrategy):
    """A definitive scraper with optimized, specific pop-up handling."""

    def __init__(self):
        super().__init__(site_name="Internshala")
        self.base_url = "https://internshala.com"

    async def _handle_popups(self, page: Page):
        """A dedicated method to find and close a specific, known pop-up."""
        
        # This is a more specific selector for the main pop-up we've observed.
        # It's less likely to conflict with other hidden elements.
        popup_selector = "#close_popup" 
        
        try:
            # Check if this specific pop-up is visible
            button = page.locator(popup_selector)
            if await button.is_visible(timeout=2000): # Short timeout
                print(f"Found and closing pop-up with selector: '{popup_selector}'")
                await button.click()
                await asyncio.sleep(0.5) # A brief pause for the page to settle after the click.
        except PlaywrightTimeoutError:
            # This is the expected outcome if the pop-up doesn't appear.
            pass

    async def scrape(self, page: Page) -> List[JobItem]:
        print(f"Scraping {self.site_name} with attribute-based selectors...")
        
        # Call our pop-up handler.
        await self._handle_popups(page)
        
        # The rest of this logic is already robust from our last iteration.
        job_card_selector = "div[internshipid]"
        
        try:
            await page.locator(job_card_selector).first.wait_for(timeout=10000)
        except PlaywrightTimeoutError:
            print("Could not find any real job cards. Assuming it's the end of results.")
            return []

        job_cards = page.locator(job_card_selector)
        count = await job_cards.count()
        print(f"Found {count} job cards (based on 'internshipid' attribute).")
        
        scraped_jobs: List[JobItem] = []
        for i in range(count):
            card = job_cards.nth(i)
            try:
                title_element = card.locator(".job-internship-name a")
                title_text = await title_element.inner_text()
                relative_url = await title_element.get_attribute("href")
                full_url = f"{self.base_url}{relative_url}"
                company_name = await card.locator("p.company-name").inner_text()
                location_elements = await card.locator("p.locations a").all()
                location_texts = [await loc.inner_text() for loc in location_elements]
                location = ", ".join(location_texts)
                salary_text_clean = None
                try:
                    salary_element = card.locator(".row-1-item span.desktop").first
                    salary_text_clean = (await salary_element.inner_text()).strip()
                except PlaywrightTimeoutError:
                    pass
                job_item = JobItem(
                    title=title_text.strip(),
                    company_name=company_name.strip(),
                    location=location,
                    raw_salary_text=salary_text_clean,
                    original_url=full_url,
                    source=self.site_name
                )
                scraped_jobs.append(job_item)
            except Exception as e:
                print(f"An unexpected error occurred processing card (nth: {i}): {e}")
                continue
                
        print(f"Successfully processed {len(scraped_jobs)} jobs from this page.")
        return scraped_jobs