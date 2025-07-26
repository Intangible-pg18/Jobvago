#similarly we can add other websites to scrape with different sets of arguments (specific to its needs for scraping
SITES_CONFIG = {
        "internshala": {
            "scraper_class_name": "InternshalaScraper",
            "module_path": "scraper_core.spiders.internshala",
            "safety_page_limit": 500,
        }
    }
SERVICE_BUS_CONFIG = {
        "queue_name": "new-jobs-queue"
}