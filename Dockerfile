# Use the official Python image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the application code
COPY . /app

# Install dependencies
RUN pip install -r requirements.txt

# Specify the command to run the operator
CMD ["python", "deployment_operator.py"]
