# This file centralizes the configuration for all scrapers.
# Adding a new website to scrape nothing but adding a new entry to this dictionary.

# Each site configuration is a dictionary with the parameters needed for its specific scraper.
# This flexible structure allows different scrapers to have different parameters.

SITES_CONFIG = {
    "internshala": {
        "scraper_class_name": "InternshalaScraper",
        "module_path": "jobvago_scraper.spiders.internshala",
        "safety_page_limit": 500,
    },
    "naukri": {
        "scraper_class_name": "NaukriScraper",
        "module_path": "jobvago_scraper.spiders.naukri",
        # A future naukri scraper might not have a page limit, maybe a "max clicks" limit.
        # The flexible config allows for this.
    }
}