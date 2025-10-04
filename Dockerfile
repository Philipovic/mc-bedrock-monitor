# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy dependency manifest first (for better caching)
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application files
COPY monitor.py /app/monitor.py

# Run the script
CMD ["python", "-u", "/app/monitor.py"]

