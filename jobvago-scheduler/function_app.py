import os
import json
import logging
import asyncio
import importlib
from typing import List, Type
from datetime import datetime
import sys

import azure.functions as func
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.identity.aio import DefaultAzureCredential
from playwright.async_api import async_playwright

# Configure logging to ensure we see output
logging.basicConfig(level=logging.INFO)

# Print the current working directory and Python path
print(f"Current directory: {os.getcwd()}")
print(f"Python path: {sys.path}")
print(f"Listing directory contents: {os.listdir('.')}")

# Try to list the scraper_core directory to verify it exists
try:
    print(f"Scraper core contents: {os.listdir('scraper_core')}")
except Exception as e:
    print(f"Error listing scraper_core: {e}")
    
# Import scraper modules with fallback config
try:
    from scraper_core.config import SITES_CONFIG, SERVICE_BUS_CONFIG
    from scraper_core.core import ScraperStrategy
    from scraper_core.models import JobItem
    logging.info("Successfully imported scraper modules")
except ImportError as e:
    logging.warning(f"Could not import scraper modules ({e}), using fallback config")
    # Fallback configuration matching your existing setup

app = func.FunctionApp()

@app.timer_trigger(schedule="0 0 */6 * * *", arg_name="myTimer", run_on_startup=True,
              use_monitor=False) 
async def ScheduledScraper(myTimer: func.TimerRequest) -> None:
    """
    Timer-triggered Azure Function that runs every 6 hours to scrape job sites.
    Schedule: "0 0 */6 * * *" means at minute 0, hour 0, every 6 hours, every day
    run_on_startup=True allows testing without waiting for the schedule
    """
    utc_timestamp = datetime.utcnow().replace(tzinfo=None).isoformat()
    
    logging.info('=== JOBVAGO SCHEDULED SCRAPER STARTED ===')
    logging.info(f'Python timer trigger function ran at {utc_timestamp}')
    
    if myTimer.past_due:
        logging.warning('The timer is past due!')
    
    try:
        # Get all configured sites to scrape
        sites_to_scrape = list(SITES_CONFIG.keys())
        logging.info(f'Configured sites to scrape: {sites_to_scrape}')
        
        all_jobs_collected = []
        scraping_summary = {}
        
        # Test Service Bus connection first
        logging.info('Testing Service Bus connection...')
        await test_service_bus_connection()
        logging.info('Service Bus connection test passed')
        
        # Scrape each configured site
        for site_name in sites_to_scrape:
            try:
                logging.info(f'=== STARTING SCRAPE: {site_name.upper()} ===')
                jobs_from_site = await run_scraper_for_site(site_name)
                all_jobs_collected.extend(jobs_from_site)
                scraping_summary[site_name] = len(jobs_from_site)
                logging.info(f'✅ {site_name}: Collected {len(jobs_from_site)} jobs')
            except Exception as site_error:
                logging.error(f'❌ {site_name}: Error occurred - {str(site_error)}', exc_info=True)
                scraping_summary[site_name] = f"ERROR: {str(site_error)}"
                # Continue with other sites even if one fails
                continue
        
        # Send all collected jobs to the Service Bus queue
        if all_jobs_collected:
            logging.info(f'=== SENDING {len(all_jobs_collected)} JOBS TO QUEUE ===')
            await send_jobs_to_queue(all_jobs_collected)
            logging.info('✅ Successfully sent all jobs to Service Bus queue')
        else:
            logging.warning('⚠️  No jobs were collected from any site')
        
        # Final summary
        logging.info('=== SCRAPING SUMMARY ===')
        for site, result in scraping_summary.items():
            logging.info(f'{site}: {result}')
        logging.info(f'Total jobs collected: {len(all_jobs_collected)}')
        logging.info('=== JOBVAGO SCHEDULED SCRAPER COMPLETED ===')
        
    except Exception as e:
        logging.error(f'💥 CRITICAL ERROR in scheduled scraper: {str(e)}', exc_info=True)
        raise


async def test_service_bus_connection():
    """
    Test the Service Bus connection to ensure configuration is correct
    """
    fqdn = os.environ.get("AZURE_SERVICE_BUS_FQDN")
    queue_name = SERVICE_BUS_CONFIG["queue_name"]
    
    if not fqdn:
        logging.error("❌ AZURE_SERVICE_BUS_FQDN environment variable not set")
        raise ValueError("Service Bus FQDN not configured")
    
    logging.info(f"🔗 Testing connection to Service Bus: '{fqdn}'")
    logging.info(f"📬 Target queue: '{queue_name}'")
    
    try:
        credential = DefaultAzureCredential()
        
        async with ServiceBusClient(fully_qualified_namespace=fqdn, credential=credential) as servicebus_client:
            sender = servicebus_client.get_queue_sender(queue_name=queue_name)
            async with sender:
                logging.info(f"✅ Successfully connected to queue '{queue_name}'")
                
    except Exception as e:
        logging.error(f"❌ Failed to connect to Service Bus: {str(e)}")
        raise


def scraper_factory(site_name: str) -> ScraperStrategy:
    """
    Factory Pattern implementation - creates the appropriate scraper for each site
    """
    if site_name not in SITES_CONFIG:
        raise ValueError(f"Unknown site: '{site_name}'. No configuration found.")

    config = SITES_CONFIG[site_name]
    module_path = config["module_path"]
    class_name = config["scraper_class_name"]

    logging.info(f"🏭 [Factory] Loading scraper: {class_name} from {module_path}")
    try:
        module = importlib.import_module(module_path)
        ScraperClass: Type[ScraperStrategy] = getattr(module, class_name)
        logging.info(f"✅ [Factory] Successfully loaded {class_name}")
        return ScraperClass()
    except (ImportError, AttributeError) as e:
        error_msg = f"Could not load scraper '{class_name}' from '{module_path}'. Error: {e}"
        logging.error(f"❌ [Factory] {error_msg}")
        raise ImportError(error_msg)


async def run_scraper_for_site(site_name: str) -> List[JobItem]:
    """
    Orchestrates scraping for a single site using the factory pattern
    """
    try:
        scraper = scraper_factory(site_name)
        all_scraped_jobs: List[JobItem] = []
        
        logging.info(f"🚀 [{site_name}] Starting browser and scraper...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            logging.info(f"🌐 [{site_name}] Browser launched successfully")
            
            job_count = 0
            async for job_item in scraper.discover_jobs(browser):
                all_scraped_jobs.append(job_item)
                job_count += 1
                if job_count % 10 == 0:  # Log every 10 jobs
                    logging.info(f"📄 [{site_name}] Scraped {job_count} jobs so far...")
            
            await browser.close()
            logging.info(f"🔒 [{site_name}] Browser closed")

        logging.info(f"✅ [{site_name}] Finished discovery. Found {len(all_scraped_jobs)} jobs total")
        return all_scraped_jobs
        
    except Exception as e:
        logging.error(f"❌ [{site_name}] Scraping failed: {str(e)}", exc_info=True)
        raise


async def send_jobs_to_queue(jobs: List[JobItem]):
    """
    Sends jobs to Azure Service Bus queue using batching for efficiency
    """
    fqdn = os.environ.get("AZURE_SERVICE_BUS_FQDN")
    queue_name = SERVICE_BUS_CONFIG["queue_name"]

    if not fqdn:
        logging.error("❌ AZURE_SERVICE_BUS_FQDN environment variable not set")
        raise ValueError("Service Bus FQDN not configured")

    logging.info(f"📤 Connecting to Service Bus: '{fqdn}'")
    logging.info(f"📬 Sending to queue: '{queue_name}'")
    
    credential = DefaultAzureCredential()
    total_sent = 0
    batch_count = 0

    async with ServiceBusClient(fully_qualified_namespace=fqdn, credential=credential) as servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name=queue_name)
        
        async with sender:
            current_batch = await sender.create_message_batch()
            batch_msg_count = 0 
            logging.info(f"📦 Starting to batch {len(jobs)} jobs...")

            for i, job in enumerate(jobs, 1):
                job_json_string = job.model_dump_json()
                message = ServiceBusMessage(job_json_string)

                try:
                    current_batch.add_message(message)
                    batch_msg_count += 1
                except ValueError:
                    # Batch is full, send it and start a new one
                    batch_count += 1
                    await sender.send_messages(current_batch)
                    total_sent += batch_msg_count
                    logging.info(f"📤 Sent batch #{batch_count} with {batch_msg_count} messages (Total sent: {total_sent})")
                    
                    current_batch = await sender.create_message_batch()
                    current_batch.add_message(message)
                    batch_msg_count = 1    

                # Log progress every 50 jobs
                if i % 50 == 0:
                    logging.info(f"📝 Processed {i}/{len(jobs)} jobs for batching...")

            # Send any remaining messages in the final batch
            if batch_msg_count > 0:
                batch_count += 1
                await sender.send_messages(current_batch)
                total_sent += batch_msg_count
                logging.info(f"📤 Sent final batch #{batch_count} with {batch_msg_count} messages")

    logging.info(f"✅ Successfully sent all {total_sent} jobs in {batch_count} batches to queue '{queue_name}'")