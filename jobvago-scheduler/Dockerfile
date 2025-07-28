# Use a standard, official Python image
FROM python:3.12-slim-bullseye

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (this step is still essential)
RUN python -m playwright install --with-deps chromium

# Copy the rest of the application code
COPY . .

# Define the command to run when the container starts
CMD ["python", "run_scraper.py"]