FROM --platform=linux/amd64 python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code
COPY src/ ./src/

# Copy the sample files
COPY sample/ ./sample/

# Command to run the application
CMD ["python", "src/main.py"]