# Korea Tourism API MCP Server

This project implements a Model Context Protocol (MCP) server that provides tools for accessing the Korea Tourism Organization's API. The server allows AI assistants to search for and retrieve information about tourist attractions, festivals, accommodations, and other tourism-related data in South Korea.

## Features

- **Multi-language Support**: Access tourism information in English, Japanese, Chinese, German, French, Spanish, and Russian (TODO: Korean)
- **Comprehensive Tourism Data**: Find attractions, cultural facilities, festivals, accommodations, restaurants, and more
- **Location-based Search**: Find tourism information based on geographic coordinates
- **Detailed Information**: Get comprehensive details including descriptions, images, addresses, and contact information

## Planned MCP Tools

Based on the functionality available in the Korea Tourism API client, we plan to implement the following MCP tools:

1. **Search Tourism by Keyword**
   - Search for tourism information using keywords
   - Filter results by content type, area, and categories

2. **Get Tourism by Area**
   - Browse tourism information by geographic areas
   - Filter by content type and categories

3. **Find Nearby Attractions**
   - Discover tourism spots near specific coordinates
   - Specify search radius and filter by attraction type

4. **Search Festivals by Date**
   - Find festivals occurring during specified date ranges
   - Filter by location

5. **Find Accommodations**
   - Search for hotels, guesthouses, and other lodging options
   - Filter by area and amenities

6. **Get Detailed Information**
   - Retrieve comprehensive details about specific tourism items
   - Access descriptions, operating hours, facilities, etc.

7. **Get Tourism Images**
   - Retrieve high-quality images for tourism attractions
   - Access both original and thumbnail images

## Requirements

- Python 3.12+
- MCP Server library
- Valid Korea Tourism API key

## Usage

The MCP server can be integrated with AI systems that support the Model Context Protocol, allowing AI assistants to access and provide detailed information about Korean tourism.

```python
# Example AI assistant query:
# "Find festivals in Seoul this summer and show me some images"

# The MCP server will provide structured data that the AI can use to respond:
{
    "festivals": [...],
    "images": [...]
}
```

## Setup

1. Obtain an API key from the Korea Tourism Organization
2. Set your API key as an environment variable
3. Start the MCP server
4. Connect your AI system to the MCP server
