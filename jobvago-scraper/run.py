import argparse
import asyncio
import importlib
from typing import List, Type

from playwright.async_api import async_playwright

from jobvago_scraper.config import SITES_CONFIG
from jobvago_scraper.core import ScraperStrategy
from jobvago_scraper.models import JobItem


def scraper_factory(site_name: str) -> ScraperStrategy:
    """
    The Factory Pattern implementation.
    Dynamically imports and instantiates the correct scraper class based on the site name.
    """
    if site_name not in SITES_CONFIG:
        raise ValueError(f"Unknown site: '{site_name}'. No configuration found.")

    config = SITES_CONFIG[site_name]
    module_path = config["module_path"]
    class_name = config["scraper_class_name"]

    print(f"[Factory] Loading scraper: {class_name} from {module_path}")
    try:
        module = importlib.import_module(module_path)
        ScraperClass: Type[ScraperStrategy] = getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Could not load scraper '{class_name}' from '{module_path}'. Error: {e}")

    return ScraperClass()


async def run_scraper_for_site(site_name: str) -> List[JobItem]:
    """
    A dedicated function to manage the scraping process for a single site.
    This version dynamically scrapes until no more jobs are found.
    """
    site_config = SITES_CONFIG[site_name]
    scraper = scraper_factory(site_name)
    all_scraped_jobs: List[JobItem] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {"image", "stylesheet", "font", "media"}
            else route.continue_()
        )

        page_number = 1
        safety_limit = site_config.get("safety_page_limit", 200) # Default to 200 if not set

        while True:
            # Safety Check: break if we exceed the safety limit
            if page_number > safety_limit:
                print(f"[{site_name}] Reached safety limit of {safety_limit} pages. Stopping.")
                break

            target_url = site_config["base_url_template"].format(page_number=page_number)
            print(f"\n[{site_name}] Navigating to page {page_number}: {target_url}")

            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=40000)
            except Exception as e:
                print(f"[{site_name}] Failed to load page {page_number}. Stopping. Error: {e}")
                break

            # The scraper does its job.
            jobs_on_page = await scraper.scrape(page)

            # The dynamic stopping condition: if the scraper returns nothing, we're done.
            if not jobs_on_page:
                print(f"[{site_name}] Scraper returned 0 jobs. Assuming this is the last page. Stopping.")
                break

            all_scraped_jobs.extend(jobs_on_page)
            print(f"[{site_name}] Total jobs collected so far: {len(all_scraped_jobs)}")

            # Increment for the next loop iteration
            page_number += 1
            await asyncio.sleep(1)

        await browser.close()
    
    return all_scraped_jobs


async def main():
    """
    The main orchestrator. Uses command-line arguments to decide which scrapers to run OR runs them all
    """
    parser = argparse.ArgumentParser(
        description="Jobvago Web Scraper: A configurable scraper for various job sites."
    )
    parser.add_argument(
        "sites",
        nargs="*", # '*' means zero or more arguments
        help="The names of the sites to scrape (e.g., internshala). If none are provided, all sites in config.py will be run."
    )
    args = parser.parse_args()

    if args.sites:
        # User specified which sites to run
        sites_to_scrape = args.sites
    else:
        # No sites specified, so run all configured sites
        print("No sites specified. Running all scrapers defined in config.py...")
        sites_to_scrape = list(SITES_CONFIG.keys())

    all_jobs: List[JobItem] = []
    for site in sites_to_scrape:
        print(f"\n--- STARTING SCRAPE FOR: {site.upper()} ---")
        try:
            jobs = await run_scraper_for_site(site)
            all_jobs.extend(jobs)
            print(f"--- FINISHED SCRAPE FOR: {site.upper()}. Found {len(jobs)} jobs. ---")
        except (ValueError, ImportError) as e:
            print(f"!!! Could not run scraper for '{site}'. Reason: {e} !!!")


    if all_jobs:
        print(f"\n\n--- SCRAPE COMPLETE ---")
        print(f"Total jobs scraped from all sites: {len(all_jobs)}")
    else:
        print("\n\n--- NO JOBS WERE SCRAPED ---")


if __name__ == "__main__":
    asyncio.run(main())