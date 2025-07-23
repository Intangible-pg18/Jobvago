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
    This orchestrator just asks the factory
    for a scraper and then collects the jobs it discovers.
    """
    scraper = scraper_factory(site_name)
    all_scraped_jobs: List[JobItem] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # The async for loop works seamlessly with our async generator.
        async for job_item in scraper.discover_jobs(browser):
            all_scraped_jobs.append(job_item)

    # High-level summary log.
    print(f"[{site_name}] Finished discovery. Found a total of {len(all_scraped_jobs)} jobs for this site.")
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