# This file centralizes the configuration for all scrapers.
# Adding a new website to scrape nothing but adding a new entry to this dictionary.

# Each site configuration is a dictionary with the parameters needed for its specific scraper.
# This flexible structure allows different scrapers to have different parameters.

SITES_CONFIG = {
    "internshala": {
        "scraper_class_name": "InternshalaScraper",
        "module_path": "jobvago_scraper.spiders.internshala",
        "base_url_template": "https://internshala.com/jobs/page-{page_number}",
        "safety_page_limit": 500,
    },
    "naukri": {
        # This is a placeholder to show how easy it is to extend the system.
        # We will implement the actual scraper for this later.
        "scraper_class_name": "NaukriScraper",
        "module_path": "jobvago_scraper.spiders.naukri",
        "base_url_template": "https://www.naukri.com/it-jobs-{page_number}",
        # We could add other params here, like 'search_keywords', if the scraper needed them.
    }
}