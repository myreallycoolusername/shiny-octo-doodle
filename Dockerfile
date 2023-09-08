#FROM debian:bullseye 
# Use the official Python image as the base image
FROM python:3.11

# Set the working directory in the container to /
WORKDIR /

# Copy the files from the current directory to the container
COPY . .

# Install the dependencies using pip
RUN pip install -r requirements.txt

# Expose port 3000 for the web server
EXPOSE 3000

# Run the main script when the container starts
CMD ["python3", "main.py"]

