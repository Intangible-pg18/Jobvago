import asyncio
from typing import AsyncGenerator
from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeoutError

from scraper_core.core import ScraperStrategy
from scraper_core.models import JobItem
from scraper_core.config import SITES_CONFIG

class InternshalaScraper(ScraperStrategy):
    """A self-sufficient scraper for Internshala."""

    def __init__(self):
        super().__init__(site_name="internshala")
        
        # The scraper now knows its own configuration and properties directly.
        # It no longer relies on the config file for its URL template.
        self.config = SITES_CONFIG[self.site_name]
        self.base_url_template = "https://internshala.com/jobs/page-{page_number}" 
        self.safety_limit = self.config.get("safety_page_limit", 500) # Use .get() for safety


    async def discover_jobs(self, browser: Browser) -> AsyncGenerator[JobItem, None]:
        """
        Implements the job discovery logic for Internshala, including pagination.
        """
        page = await browser.new_page()
        await page.route("**/*", lambda route: route.abort() if route.request.resource_type in {"image", "stylesheet", "font", "media"} else route.continue_())

        page_number = 1
        total_jobs_discovered = 0

        while page_number <= self.safety_limit:
            target_url = self.base_url_template.format(page_number=page_number)
            print(f"\n[{self.site_name}] Navigating to page {page_number}: {target_url}")

            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=40000)
            except Exception as e:
                print(f"[{self.site_name}] Failed to load page {page_number}. Stopping. Error: {e}")
                break

            jobs_found_on_page = await self._parse_page(page)
            if not jobs_found_on_page:
                print(f"[{self.site_name}] No valid jobs parsed. Assuming end of results.")
                break
            
            for job_item in jobs_found_on_page:
                yield job_item
                total_jobs_discovered += 1

            print(f"[{self.site_name}] Total jobs discovered so far: {total_jobs_discovered}")

            page_number += 1
            await asyncio.sleep(1)
        
        await page.close()

    async def _parse_page(self, page: Page) -> list[JobItem]:
        """A helper method to parse a single page for job cards."""
        await self._handle_popups(page)
        
        job_card_selector = "div[internshipid]"
        try:
            await page.locator(job_card_selector).first.wait_for(timeout=10000)
        except PlaywrightTimeoutError:
            return []

        job_cards = page.locator(job_card_selector)
        count = await job_cards.count()
        print(f"[{self.site_name}] Found {count} potential job cards on the page.")
        
        scraped_jobs_on_page = []
        for i in range(count):
            card = job_cards.nth(i)
            try:
                title_element = card.locator(".job-internship-name a")
                title_text = await title_element.inner_text()
                relative_url = await title_element.get_attribute("href")
                
                job_item = JobItem(
                    title=title_text.strip(),
                    company_name=await card.locator("p.company-name").inner_text(),
                    location=", ".join([await loc.inner_text() for loc in await card.locator("p.locations a").all()]),
                    raw_salary_text=(await card.locator(".row-1-item span.desktop").first.inner_text()).strip(),
                    original_url=f"https://internshala.com{relative_url}",
                    source=self.site_name
                )
                scraped_jobs_on_page.append(job_item)
            except Exception:
                continue
        
        print(f"[{self.site_name}] Successfully processed {len(scraped_jobs_on_page)} valid job cards.")
        return scraped_jobs_on_page

    async def _handle_popups(self, page: Page):
        """Pop-up handling logic"""
        popup_selector = "#close_popup"
        try:
            button = page.locator(popup_selector)
            if await button.is_visible(timeout=2000):
                await button.click()
                await asyncio.sleep(0.5)
        except PlaywrightTimeoutError:
            pass