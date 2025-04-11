# Korea Tourism API MCP Server ✈️

<!-- Badges -->
[![smithery badge](https://smithery.ai/badge/@harimkang/mcp-korea-tourism-api)](https://smithery.ai/interface/@harimkang/mcp-korea-tourism-api)
[![PyPI version](https://badge.fury.io/py/mcp-korea-tourism-api.svg)](https://badge.fury.io/py/mcp-korea-tourism-api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI Tests](https://github.com/harimkang/mcp-korea-tourism-api/actions/workflows/ci.yml/badge.svg)](https://github.com/harimkang/mcp-korea-tourism-api/actions/workflows/ci.yml)


Unlock the wonders of South Korean tourism directly within your AI assistant! This project provides a Model Context Protocol (MCP) server powered by the official Korea Tourism Organization (KTO) API. Equip your AI with the ability to discover vibrant festivals, serene temples, delicious restaurants, comfortable accommodations, and much more across Korea.

**Links:**
*   **PyPI Package:** [https://pypi.org/project/mcp-korea-tourism-api/](https://pypi.org/project/mcp-korea-tourism-api/)
*   **GitHub Repository:** [https://github.com/harimkang/mcp-korea-tourism-api](https://github.com/harimkang/mcp-korea-tourism-api)
*   **Releases:** [https://github.com/harimkang/mcp-korea-tourism-api/releases](https://github.com/harimkang/mcp-korea-tourism-api/releases)


## ✨ Features

- **Comprehensive Search:** Find tourist spots, cultural sites, events, food, lodging, and shopping via keywords, area, or location.
- **Rich Details:** Access descriptions, operating hours, admission fees, photos, addresses, and contact information.
- **Location-Aware:** Discover attractions near specific GPS coordinates.
- **Timely Information:** Find festivals and events based on date ranges.
- **Multilingual Support:** Get information in various languages supported by the KTO API (including English).
    - **Supported Languages**: English, Japanese, Simplified Chinese, Traditional Chinese, Russian, Spanese, German, French
- **Efficient & Resilient:** 
    - **Response Caching:** Uses time-to-live (TTL) caching to store results and reduce redundant API calls, improving speed.
    - **Rate Limiting:** Respects API usage limits to prevent errors.
    - **Automatic Retries:** Automatically retries requests in case of temporary network or server issues.
- **MCP Standard:** Seamlessly integrates with AI assistants supporting the Model Context Protocol.

## ⚠️ Prerequisites

Before you begin, you **must** obtain an API key from the **Korea Tourism Organization (KTO) Data Portal**.

1.  Visit the [KTO Data Portal](https://www.data.go.kr/) (or the specific portal for the tourism API if available).
2.  Register and request an API key for the "TourAPI" services (you might need to look for services providing information like `areaBasedList`, `searchKeyword`, `detailCommon`, etc.).
3.  Keep your **Service Key (API Key)** safe. It will be required during installation or runtime.


> You need to apply for the API below to make a request for each language.
> * English: https://www.data.go.kr/data/15101753/openapi.do
> * Japanese: https://www.data.go.kr/data/15101760/openapi.do
> * Simplified Chinese: https://www.data.go.kr/data/15101764/openapi.do
> * Traditional Chinese: https://www.data.go.kr/data/15101769/openapi.do
> * Russian: https://www.data.go.kr/data/15101831/openapi.do
> * Spanese: https://www.data.go.kr/data/15101811/openapi.do
> * German: https://www.data.go.kr/data/15101805/openapi.do
> * French: https://www.data.go.kr/data/15101808/openapi.do


## 🚀 Installation & Running

You can run this MCP server using either `uv` (a fast Python package installer and runner) or `Docker`.

### Installing via Smithery

To install Korea Tourism API MCP Server for Claude Desktop automatically via [Smithery](https://smithery.ai/interface/@harimkang/mcp-korea-tourism-api):

```bash
npx -y @smithery/cli install @harimkang/mcp-korea-tourism-api --client claude
```
### Option 1: Using `uv` (Recommended for local development)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/harimkang/mcp-korea-tourism-api.git
    cd mcp-korea-tourism-api
    ```
2.  **Set the API Key Environment Variable:**
    Replace `"YOUR_KTO_API_KEY"` with the actual key you obtained.
    ```bash
    # On macOS/Linux
    export KOREA_TOURISM_API_KEY="YOUR_KTO_API_KEY"

    # On Windows (Command Prompt)
    # set KOREA_TOURISM_API_KEY="YOUR_KTO_API_KEY"

    # On Windows (PowerShell)
    # $env:KOREA_TOURISM_API_KEY="YOUR_KTO_API_KEY"
    ```
    *Note: For persistent storage, add this line to your shell's configuration file (e.g., `.zshrc`, `.bashrc`, or use system environment variable settings).*

3.  **Install dependencies and run the server:**
    This command uses `uv` to install dependencies based on `uv.lock` (if available) or `pyproject.toml` and then runs the server module.
    ```bash
    uv run -m mcp_tourism.server
    ```
    The server will start and listen for MCP requests via standard input/output (stdio).

### Option 2: Using Docker (Recommended for isolated environment/deployment)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/harimkang/mcp-korea-tourism-api.git
    cd mcp-korea-tourism-api
    ```
2.  **Build the Docker Image:**
    Replace `"YOUR_KTO_API_KEY"` with the actual key you obtained. This command builds the image using the provided `Dockerfile`, passing the API key securely as a build argument.
    ```bash
    >>> docker build -t mcp-korea-tourism .

    [+] Building 2.7s (13/13) FINISHED                                                 docker:desktop-linux
    => [internal] load build definition from Dockerfile                                               0.0s
    => => transferring dockerfile: 1.46kB                                                             0.0s
    => resolve image config for docker-image://docker.io/docker/dockerfile:1                          0.9s
    => CACHED docker-image://docker.io/docker/dockerfile:1@sha256:4c68376a702446fc3c79af22de146a148b  0.0s
    => [internal] load metadata for docker.io/library/python:3.12-slim                                0.7s
    => [internal] load .dockerignore                                                                  0.0s
    => => transferring context: 864B                                                                  0.0s
    => [1/6] FROM docker.io/library/python:3.12-slim@sha256:85824326bc4ae27a1abb5bc0dd9e08847aa5fe73  0.0s
    => [internal] load build context                                                                  0.0s
    => => transferring context: 7.06kB                                                                0.0s
    => CACHED [2/6] RUN pip install --no-cache-dir uv                                                 0.0s
    => CACHED [3/6] WORKDIR /app                                                                      0.0s
    => CACHED [4/6] COPY pyproject.toml uv.lock ./                                                    0.0s
    => [5/6] RUN uv sync --frozen                                                                     0.8s
    => [6/6] COPY . .                                                                                 0.0s
    => exporting to image                                                                             0.1s
    => => exporting layers                                                                            0.1s
    => => writing image sha256:d7d074e85a66a257d00bad4043ea0f5ba8acf6b7c6ef26560c6904bf3ec4d5ff       0.0s 
    => => naming to docker.io/library/mcp-korea-tourism                                               0.0s

    >>> docker images

    REPOSITORY                              TAG                IMAGE ID       CREATED          SIZE
    mcp-korea-tourism                       latest             d7d074e85a66   12 seconds ago   215MB
    ```
    * `-t mcp-korea-tourism`: Tags the built image with the name `mcp-korea-tourism`.
    * `.`: Specifies the current directory as the build context.

3.  **Run the Docker Container:**
    You can run the container in interactive mode for testing or detached mode for background operation.

    *   **Interactive Mode (for manual testing):**
        ```bash
        docker run --rm -it -e KOREA_TOURISM_API_KEY="YOUR_KTO_API_KEY" mcp-korea-tourism
        ```
        * `--rm`: Automatically removes the container when it exits.
        * `-it`: Runs in interactive mode, attaching your terminal to the container's stdio.
        * `-e KOREA_TOURISM_API_KEY=...`: Sets the API key environment variable at runtime (alternative to build-arg).

    *   **Detached Mode (for background):**
        ```bash
        docker run --name tourism-mcp -d -e KOREA_TOURISM_API_KEY="YOUR_KTO_API_KEY" mcp-korea-tourism
        ```
        * `--name tourism-mcp`: Assigns a name to the container.
        * `-d`: Runs the container in detached (background) mode.
        * You can view logs using `docker logs tourism-mcp`.

## 🛠️ Integrating with Cursor

To use this MCP server within Cursor:

1.  **Ensure the Docker container is runnable:** Follow the Docker installation steps above to build the image (`mcp-korea-tourism`). You don't need to manually run the container; Cursor will do that.
2.  **Locate your `mcp.json` file:** This file configures MCP tools for Cursor. You can usually find it via Cursor's settings or potentially in a path like `~/.cursor/mcp.json` or similar.
3.  **Add or Update the MCP Configuration:** Add the following JSON object to the list within your `mcp.json` file. If you already have an entry for this tool, update its `command`. Replace `"YOUR_KTO_API_KEY"` with your actual key.
    ![cursor_integrations](images/cursor_integration.png)

    ```json
    {
        "mcpServers": {
            "korea-tourism": {
                "command": "docker",
                "args": [
                    "run",
                    "--rm",
                    "-i",
                    "-e",
                    "KOREA_TOURISM_API_KEY=YOUR_KTO_API_KEY",
                    "mcp-korea-tourism"
                ]
            }
        }
    }
    ```

    OR Use uv [local directory]
    ```json
    {
        "mcpServers": {
            "korea-tourism": {
                "command": "uv",
                "args": [
                    "--directory",
                    "{LOCAL_PATH}/mcp-korea-tourism-api",
                    "run",
                    "-m",
                    "mcp_tourism.server"
                ],
                "env": {
                    "KOREA_TOURISM_API_KEY": "YOUR_KTO_API_KEY"
                }
            }
        }
    }
    ```

4.  **Save `mcp.json`**.
5.  **Restart Cursor or Reload MCP Tools:** Cursor should now detect the tool and use Docker to run it when needed.

## 🛠️ MCP Tools Provided

This server exposes the following tools for AI assistants:

1.  `search_tourism_by_keyword`: Search for tourism information using keywords (e.g., "Gyeongbokgung", "Bibimbap"). Filter by content type, area code.
    ![search_tourism_by_keyword](images/search_tourism_by_keyword.png)
2.  `get_tourism_by_area`: Browse tourism information by geographic area codes (e.g., Seoul='1'). Filter by content type, district code.
    ![get_tourism_by_area](images/get_tourism_by_area.png)
3.  `find_nearby_attractions`: Discover tourism spots near specific GPS coordinates (longitude, latitude). Filter by radius and content type.
    ![find_nearby_attractions](images/find_nearby_attractions.png)
4.  `search_festivals_by_date`: Find festivals occurring within a specified date range (YYYYMMDD). Filter by area code.
    ![search_festivals_by_date](images/search_festivals_by_date.png)
5.  `find_accommodations`: Search for hotels, guesthouses, etc. Filter by area and district code.
    ![find_accommodations](images/find_accommodations.png)
6.  `get_detailed_information`: Retrieve comprehensive details (overview, usage time, parking, etc.) for a specific item using its Content ID. Filter by content type.
    ![get_detailed_information](images/get_detailed_information.png)
7.  `get_tourism_images`: Get image URLs associated with a specific tourism item using its Content ID.
    ![get_tourism_images](images/get_tourism_images.png)
8.  `get_area_codes`: Retrieve area codes (for cities/provinces) and optionally sub-area (district) codes.
    ![get_area_codes](images/get_area_codes.png)

## ⚙️ Requirements (for `uv` method)

- Python 3.12+
- `uv` installed (`pip install uv`)

## Example Usage

An AI assistant integrated with this MCP could handle queries like:

*   "Find restaurants near Myeongdong station."
*   "Show me pictures of Bulguksa Temple."
*   "Are there any festivals in Busan next month?"
*   "Tell me more about Gyeongbokgung Palace, content ID 264337."
