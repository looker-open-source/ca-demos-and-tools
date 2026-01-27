# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Install the application
RUN pip install -e .

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable
ENV PYTHONUNBUFFERED=1

# Run the application using Gunicorn
# Workers=1 to prevent multiple backend dispatchers (if applicable, though Prism UI seems stateless mostly)
# Threads=8 for concurrency
# Timeout=0 to allow long-running requests (if any)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "prism.prod:app"]
