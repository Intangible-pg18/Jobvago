import os
import json
import logging
import asyncio
import importlib
from typing import List, Type
from datetime import datetime

import azure.functions as func

# Azure Service Bus imports with error handling
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.identity.aio import DefaultAzureCredential

# Playwright import with error handling
from playwright.async_api import async_playwright

# Import scraper modules - we'll need to adapt these paths
from scraper_core.config import SITES_CONFIG, SERVICE_BUS_CONFIG
from scraper_core.core import ScraperStrategy
from scraper_core.models import JobItem

app = func.FunctionApp()

@app.timer_trigger(schedule="0 0 */6 * * *", arg_name="myTimer", run_on_startup=True,
              use_monitor=False) 
async def ScheduledScraper(myTimer: func.TimerRequest) -> None:
    """
    Timer-triggered Azure Function that runs every 6 hours to scrape job sites.
    Schedule: "0 0 */6 * * *" means at minute 0, hour 0, every 6 hours, every day
    """
    utc_timestamp = datetime.utcnow().replace(tzinfo=None).isoformat()
    
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function ran at %s', utc_timestamp)
    logging.info('Starting scheduled job scraping...')
    
    try:
        # For initial testing, let's just log that the function is working
        # and try a simple Service Bus connection test
        await test_service_bus_connection()
        
        # Later, we'll uncomment this to run the full scraping logic
        # await run_full_scraping_pipeline()
        
        logging.info('Scheduled scraper completed successfully')
        
    except Exception as e:
        logging.error(f'Critical error in scheduled scraper: {str(e)}', exc_info=True)
        raise


async def test_service_bus_connection():
    """
    Test the Service Bus connection without running the full scraper
    """
    fqdn = os.environ.get("AZURE_SERVICE_BUS_FQDN")
    queue_name = SERVICE_BUS_CONFIG["queue_name"]
    
    if not fqdn:
        logging.error("AZURE_SERVICE_BUS_FQDN environment variable not set")
        raise ValueError("Service Bus FQDN not configured")
    
    logging.info(f"Testing connection to Service Bus: '{fqdn}'")
    
    try:
        credential = DefaultAzureCredential()
        
        async with ServiceBusClient(fully_qualified_namespace=fqdn, credential=credential) as servicebus_client:
            # Just test that we can create a sender - don't send anything yet
            sender = servicebus_client.get_queue_sender(queue_name=queue_name)
            async with sender:
                logging.info(f"Successfully connected to queue '{queue_name}'")
                
    except Exception as e:
        logging.error(f"Failed to connect to Service Bus: {str(e)}")
        raise


async def run_full_scraping_pipeline():
    """
    The full scraping pipeline - commented out for initial testing
    """
    # Get all configured sites to scrape
    sites_to_scrape = list(SITES_CONFIG.keys())
    logging.info(f'Configured sites to scrape: {sites_to_scrape}')
    
    all_jobs_collected = []
    
    # Scrape each configured site
    for site_name in sites_to_scrape:
        try:
            logging.info(f'Starting to scrape: {site_name}')
            jobs_from_site = await run_scraper_for_site(site_name)
            all_jobs_collected.extend(jobs_from_site)
            logging.info(f'Collected {len(jobs_from_site)} jobs from {site_name}')
        except Exception as site_error:
            logging.error(f'Error scraping {site_name}: {str(site_error)}')
            continue
    
    # Send all collected jobs to the Service Bus queue
    if all_jobs_collected:
        await send_jobs_to_queue(all_jobs_collected)
        logging.info(f'Successfully sent {len(all_jobs_collected)} total jobs to queue')
    else:
        logging.warning('No jobs were collected from any site')


def scraper_factory(site_name: str) -> ScraperStrategy:
    """
    Factory Pattern implementation - adapted from run.py
    """
    if site_name not in SITES_CONFIG:
        raise ValueError(f"Unknown site: '{site_name}'. No configuration found.")

    config = SITES_CONFIG[site_name]
    module_path = config["module_path"]
    class_name = config["scraper_class_name"]

    logging.info(f"[Factory] Loading scraper: {class_name} from {module_path}")
    try:
        module = importlib.import_module(module_path)
        ScraperClass: Type[ScraperStrategy] = getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Could not load scraper '{class_name}' from '{module_path}'. Error: {e}")

    return ScraperClass()


async def run_scraper_for_site(site_name: str) -> List[JobItem]:
    """
    Orchestrates scraping for a single site - adapted from run.py
    """
    scraper = scraper_factory(site_name)
    all_scraped_jobs: List[JobItem] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        async for job_item in scraper.discover_jobs(browser):
            all_scraped_jobs.append(job_item)
        
        await browser.close()

    logging.info(f"[{site_name}] Finished discovery. Found {len(all_scraped_jobs)} jobs")
    return all_scraped_jobs


async def send_jobs_to_queue(jobs: List[JobItem]):
    """
    Sends jobs to Azure Service Bus queue - adapted from run.py
    """
    fqdn = os.environ.get("AZURE_SERVICE_BUS_FQDN")
    queue_name = SERVICE_BUS_CONFIG["queue_name"]

    if not fqdn:
        logging.error("AZURE_SERVICE_BUS_FQDN environment variable not set")
        raise ValueError("Service Bus FQDN not configured")

    logging.info(f"Connecting to Service Bus: '{fqdn}'")
    
    credential = DefaultAzureCredential()

    async with ServiceBusClient(fully_qualified_namespace=fqdn, credential=credential) as servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name=queue_name)
        
        async with sender:
            current_batch = await sender.create_message_batch()
            logging.info(f"Sending {len(jobs)} jobs to queue '{queue_name}'")

            for job in jobs:
                job_json_string = job.model_dump_json()
                message = ServiceBusMessage(job_json_string)

                try:
                    current_batch.add_message(message)
                except ValueError:
                    # Batch is full, send it and start a new one
                    await sender.send_messages(current_batch)
                    logging.info("Sent a full batch, starting new batch")
                    current_batch = await sender.create_message_batch()
                    current_batch.add_message(message)

            # Send any remaining messages in the final batch
            if current_batch.message_count > 0:
                await sender.send_messages(current_batch)
                logging.info(f"Sent final batch with {current_batch.message_count} messages")