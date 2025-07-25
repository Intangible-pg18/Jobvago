import os
import json
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

import argparse
import asyncio
import importlib
from typing import List, Type

from playwright.async_api import async_playwright

from jobvago_scraper.config import SITES_CONFIG
from jobvago_scraper.config import SITES_CONFIG, SERVICE_BUS_CONFIG
from jobvago_scraper.core import ScraperStrategy
from jobvago_scraper.models import JobItem

load_dotenv()

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

async def send_jobs_to_queue(jobs: List[JobItem]):
    """
    Connects to Azure Service Bus and sends a list of jobs to the queue using batching.
    """
    # Getting the FQDN from the environment variable we set
    fqdn = os.environ.get("AZURE_SERVICE_BUS_FQDN")
    queue_name = SERVICE_BUS_CONFIG["queue_name"]

    if not fqdn:
        print("!!! ERROR: AZURE_SERVICE_BUS_FQDN environment variable not set. Cannot send messages. !!!")
        return

    print(f"\nConnecting to Service Bus: '{fqdn}'...")
    
    # Using DefaultAzureCredential for passwordless, secure authentication
    credential = DefaultAzureCredential()

    async with ServiceBusClient(fully_qualified_namespace=fqdn, credential=credential) as servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name=queue_name)
        
        async with sender:
            # Creating a message batch
            current_batch = await sender.create_message_batch()
            print(f"Sending {len(jobs)} jobs to queue '{queue_name}'...")

            for job in jobs:
                # Serializing the Pydantic model to a JSON string
                job_json_string = job.model_dump_json()
                message = ServiceBusMessage(job_json_string)

                try:
                    # Tring to add the message to the current batch
                    current_batch.add_message(message)
                except ValueError:
                    # The current batch is full. Sending it.
                    print(f"Batch is full. Sending {len(current_batch)} messages...")
                    await sender.send_messages(current_batch)
                    
                    # Creating a new batch and adding the message that didn't fit
                    current_batch = await sender.create_message_batch()
                    current_batch.add_message(message)

            # Sending any remaining messages in the last batch
            if len(current_batch) > 0:
                print(f"Sending final batch of {len(current_batch)} messages...")
                await sender.send_messages(current_batch)

    print("All jobs sent to the queue successfully.")
    await credential.close()

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
            if jobs:
                await send_jobs_to_queue(jobs)
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