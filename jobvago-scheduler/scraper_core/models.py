from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime

class JobItem(BaseModel):
    title: str = Field(..., description="The title of the job posting")
    company_name: str = Field(..., description="The name of the company.")
    location: str = Field(..., description="The primary location of the job, e.g., 'Mumbai'.")

    raw_salary_text: Optional[str] = Field(None, description="The original, unprocessed salary string, e.g., '₹ 5 - 7 LPA'.")
    
    original_url: HttpUrl = Field(..., description="The direct URL to the job posting.")
    
    description: Optional[str] = Field(None, description="The full description of the job.")
    
    skills: Optional[List[str]] = Field(None, description="A list of required skills.")
    posted_date: Optional[datetime] = Field(None, description="The date the job was originally posted.")
    
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="The timestamp when this item was scraped.")
    source: str = Field(..., description="The name of the source website, e.g., 'Internshala'.")