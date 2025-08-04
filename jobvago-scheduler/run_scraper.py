import os
import asyncio
import json
import logging
import importlib
from typing import List, Type
from datetime import datetime

from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from playwright.async_api import async_playwright
from azure.identity.aio import DefaultAzureCredential

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

from scraper_core.config import SITES_CONFIG, SERVICE_BUS_CONFIG
from scraper_core.core import ScraperStrategy
from scraper_core.models import JobItem

logging.info("Successfully imported scraper modules.")


async def test_service_bus_connection():
    """Validates the Service Bus connection using Managed Identity."""
    logging.info("Testing Service Bus connection using Managed Identity...")
    
    service_bus_fqdn = os.environ.get("SERVICE_BUS_FQDN") 
    if not service_bus_fqdn:
        logging.error("FATAL: SERVICE_BUS_FQDN environment variable is not set.")
        raise ValueError("SERVICE_BUS_FQDN is not configured.")
        
    credential = DefaultAzureCredential() 
    
    try:
        async with ServiceBusClient(fully_qualified_namespace=service_bus_fqdn, credential=credential) as client:
            pass 
        logging.info("✅ Service Bus connection test passed.")
    except Exception as e:
        logging.error(f"❌ Failed to connect to Service Bus using Managed Identity: {e}", exc_info=True)
        raise

def scraper_factory(site_name: str) -> ScraperStrategy:
    """Instantiates and returns the correct scraper based on the site name."""
    logging.info(f"🏭 [Factory] Creating scraper for '{site_name}'.")
    config = SITES_CONFIG[site_name]
    module_path = config["module_path"]
    class_name = config["scraper_class_name"]
    try:
        module = importlib.import_module(module_path)
        ScraperClass: Type[ScraperStrategy] = getattr(module, class_name)
        logging.info(f"✅ [Factory] Successfully loaded {class_name}.")
        return ScraperClass()
    except (ImportError, AttributeError) as e:
        logging.error(f"❌ [Factory] Could not load scraper '{class_name}' from '{module_path}'.", exc_info=True)
        raise

async def run_scraper_for_site(site_name: str) -> List[JobItem]:
    """Orchestrates the Playwright browser automation for a single site."""
    scraper = scraper_factory(site_name)
    all_scraped_jobs: List[JobItem] = []
    
    logging.info(f"🚀 [{site_name}] Starting browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        logging.info(f"🌐 [{site_name}] Browser launched successfully.")
        
        job_count = 0
        async for job_item in scraper.discover_jobs(browser):
            all_scraped_jobs.append(job_item)
            job_count += 1
            if job_count % 10 == 0:
                logging.info(f"📄 [{site_name}] Scraped {job_count} jobs so far...")
        
        await browser.close()
        logging.info(f"🔒 [{site_name}] Browser closed.")

    logging.info(f"✅ [{site_name}] Finished discovery. Found {len(all_scraped_jobs)} jobs.")
    return all_scraped_jobs

async def send_jobs_to_queue(jobs: List[JobItem]):
    """Serializes and sends jobs to the queue using Managed Identity."""
    
    service_bus_fqdn = os.environ.get("SERVICE_BUS_FQDN")
    queue_name = SERVICE_BUS_CONFIG["queue_name"]
    
    credential = DefaultAzureCredential()

    logging.info(f"📤 Sending {len(jobs)} jobs to '{queue_name}' using Managed Identity...")
    
    async with ServiceBusClient(fully_qualified_namespace=service_bus_fqdn, credential=credential) as client:
        sender = client.get_queue_sender(queue_name=queue_name)
        async with sender:
            current_batch = await sender.create_message_batch()
            for job in jobs:
                message = ServiceBusMessage(job.model_dump_json())
                try:
                    current_batch.add_message(message)
                except ValueError:
                    await sender.send_messages(current_batch)
                    current_batch = await sender.create_message_batch()
                    current_batch.add_message(message)
            if len(current_batch) > 0:
                await sender.send_messages(current_batch)
    
    logging.info(f"✅ Successfully sent all {len(jobs)} jobs.")


async def main():
    """The primary function that orchestrates the entire scraping job."""
    logging.info('=' * 50)
    logging.info('=== JOBVAGO CONTAINERIZED SCRAPER JOB STARTED ===')
    logging.info('=' * 50)
    
    try:
        await test_service_bus_connection()
        
        sites_to_scrape = list(SITES_CONFIG.keys())
        all_jobs_collected = []
        scraping_summary = {}
        
        for site_name in sites_to_scrape:
            try:
                logging.info(f"{'-'*20} Starting scrape for: {site_name.upper()} {'-'*20}")
                jobs_from_site = await run_scraper_for_site(site_name)
                all_jobs_collected.extend(jobs_from_site)
                scraping_summary[site_name] = f"OK - Collected {len(jobs_from_site)} jobs"
            except Exception:
                logging.error(f"Scraping failed for site '{site_name}'.", exc_info=True)
                scraping_summary[site_name] = "ERROR - See logs for details"
        
        if all_jobs_collected:
            await send_jobs_to_queue(all_jobs_collected)
        else:
            logging.warning('⚠️  No jobs were collected from any site. Nothing to send.')
            
        logging.info('=' * 50)
        logging.info('--- SCRAPING SUMMARY ---')
        for site, result in scraping_summary.items():
            logging.info(f'{site}: {result}')
        logging.info(f"Total jobs collected: {len(all_jobs_collected)}")
        logging.info('=' * 50)

    except Exception as e:
        logging.critical(f"A fatal error occurred in the main job execution: {e}", exc_info=True)
        exit(1)
        
    logging.info('=== JOBVAGO CONTAINERIZED SCRAPER JOB COMPLETED SUCCESSFULLY ===')

if __name__ == "__main__":
    asyncio.run(main())
