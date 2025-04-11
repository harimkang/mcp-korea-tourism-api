# syntax=docker/dockerfile:1

# Use the Python version confirmed from .python-version
FROM python:3.12-slim

# Install uv
# --no-cache-dir reduces image size
RUN pip install --no-cache-dir uv

# Set the working directory in the container
WORKDIR /app

# Copy dependency files first to leverage Docker cache
COPY pyproject.toml ./

# Generate requirements.txt from pyproject.toml dependencies section directly
# This avoids trying to find the local project and only focuses on external dependencies
RUN python -c "import tomllib; deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; print('\n'.join(deps))" > requirements.txt

# Install dependencies using pip from the requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application source code (including the src directory)
COPY . .

# Install the project itself from the src directory
# This makes the mcp_tourism package available to the Python interpreter
# --no-deps prevents reinstalling already synced dependencies
# --system is required because we are not in a virtual environment
RUN uv pip install . --no-deps --system

# Set the API key as an environment variable
# IMPORTANT: It's strongly recommended to pass the API key securely at runtime using -e.
# Example runtime command: docker run -e KOREA_TOURISM_API_KEY="YOUR_ACTUAL_API_KEY" ...
# ENV KOREA_TOURISM_API_KEY="YOUR_ACTUAL_API_KEY" # Avoid hardcoding if possible

# Expose the port the MCP server might run on (if applicable)
# Adjust the port number if your server uses a different one.
# EXPOSE 8000

# Command to run the application
# Use python -m directly instead of uv run to avoid creating a virtual env at runtime
CMD ["python", "-m", "mcp_tourism.server"] 