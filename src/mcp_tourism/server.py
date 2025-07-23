# server.py
from typing import List
import os
import atexit
import signal
import asyncio
import argparse
import sys
from typing import Dict, Any, Optional
from fastmcp import FastMCP
from mcp_tourism.api_client import KoreaTourismApiClient, CONTENTTYPE_ID_MAP
import logging
from starlette.requests import Request
from starlette.responses import JSONResponse


# Create an MCP server
mcp = FastMCP(
    name="Korea Tourism API",
    dependencies=["httpx", "cachetools", "tenacity", "ratelimit"],
)

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Lazy initialization of the API client
_api_client: Optional[KoreaTourismApiClient] = None


def get_api_client() -> KoreaTourismApiClient:
    """
    Lazily initialize the API client only when needed.
    Reads configuration from environment variables.
    """
    global _api_client
    if _api_client is None:
        # Get API key from environment variable
        api_key = os.environ.get("KOREA_TOURISM_API_KEY")

        if not api_key:
            logger.warning(
                "KOREA_TOURISM_API_KEY environment variable is not set. "
                "API calls will fail until a valid key is provided."
            )
            api_key = "missing_api_key"  # Placeholder that will cause API calls to fail properly

        # Get configuration from environment variables with defaults
        default_language = os.environ.get("MCP_TOURISM_DEFAULT_LANGUAGE", "en")
        cache_ttl = int(os.environ.get("MCP_TOURISM_CACHE_TTL", 86400))
        rate_limit_calls = int(os.environ.get("MCP_TOURISM_RATE_LIMIT_CALLS", 5))
        rate_limit_period = int(os.environ.get("MCP_TOURISM_RATE_LIMIT_PERIOD", 1))
        concurrency_limit = int(os.environ.get("MCP_TOURISM_CONCURRENCY_LIMIT", 10))

        logger.info("Initializing KoreaTourismApiClient with:")
        logger.info(f"  Default Language: {default_language}")
        logger.info(f"  Cache TTL: {cache_ttl}s")
        logger.info(f"  Rate Limit: {rate_limit_calls} calls / {rate_limit_period}s")
        logger.info(f"  Concurrency Limit: {concurrency_limit}")

        # Initialize the client
        try:
            _api_client = KoreaTourismApiClient(
                api_key=api_key,
                language=default_language,
                cache_ttl=cache_ttl,
                rate_limit_calls=rate_limit_calls,
                rate_limit_period=rate_limit_period,
                concurrency_limit=concurrency_limit,
            )
            # Trigger initialization check which also validates API key early
            _api_client._ensure_full_initialization()
            logger.info("KoreaTourismApiClient initialized successfully.")
        except ValueError as e:
            logger.error(f"Failed to initialize KoreaTourismApiClient: {e}")
            # Propagate the error so the MCP tool call fails clearly
            raise
    return _api_client


# Resource cleanup functions
def cleanup_resources():
    """
    Clean up resources when the server shuts down.
    This function is called by atexit and signal handlers.
    """
    logger.info("Cleaning up resources...")
    try:
        # Try to get the current event loop
        try:
            loop = asyncio.get_event_loop()
            # Check if the loop is closed
            if loop.is_closed():
                logger.info("Event loop is already closed, skipping async cleanup")
                return
        except RuntimeError:
            # No event loop exists - this is common during process shutdown
            logger.info("No event loop available, creating temporary loop for cleanup")
            try:
                # Create a temporary event loop for cleanup
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        KoreaTourismApiClient.close_all_connections()
                    )
                    logger.info("Resources cleaned up successfully.")
                finally:
                    loop.close()
                return
            except Exception as temp_loop_error:
                logger.warning(f"Temporary loop cleanup failed: {temp_loop_error}")
                logger.info(
                    "Skipping resource cleanup - connections will be closed by OS"
                )
                return

        if loop.is_running():
            # If we're in a running event loop, schedule the cleanup
            # Note: This scenario is tricky - we can't wait for completion
            logger.warning("Event loop is running, scheduling cleanup task")
            loop.create_task(KoreaTourismApiClient.close_all_connections())
        else:
            # Loop exists and is not running, safe to run_until_complete
            loop.run_until_complete(KoreaTourismApiClient.close_all_connections())

        logger.info("Resources cleaned up successfully.")
    except Exception as e:
        logger.warning(f"Resource cleanup failed: {e}")
        logger.info("Connections will be closed automatically by the operating system")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    cleanup_resources()
    os._exit(0)


# Register cleanup handlers
atexit.register(cleanup_resources)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# MCP Tools for Korea Tourism API
@mcp.tool
async def search_tourism_by_keyword(
    keyword: str,
    content_type: str | None = None,
    area_code: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
    filter: List[str] | None = None,
) -> dict:
    """
    Search for tourism information in Korea by keyword.

    This tool searches through the Korea Tourism Organization database for tourism items
    matching the specified keyword. It supports filtering by content type, area, and
    provides paginated results with detailed information.

    Args:
        keyword (str): Search keyword (e.g., "Gyeongbokgung", "Hanok", "Bibimbap")
        content_type (str, optional): Type of content to search for. Valid values:
            - "Tourist Attraction" (default)
            - "Cultural Facility"
            - "Festival Event"
            - "Leisure Activity"
            - "Accommodation"
            - "Shopping"
            - "Restaurant"
            - "Transportation"
        area_code (str, optional): Area code to filter results. Valid values:
            - "1" (Seoul)
            - "2" (Incheon)
            - "3" (Daejeon)
            - "4" (Daegu)
            - "5" (Gwangju)
            - "6" (Busan)
            - "7" (Ulsan)
            - "8" (Sejong)
            - "31" (Gyeonggi-do)
            - "32" (Gangwon-do)
            - "33" (Chungcheongbuk-do)
            - "34" (Chungcheongnam-do)
            - "35" (Gyeongsangbuk-do)
            - "36" (Gyeongsangnam-do)
            - "37" (Jeonbuk-do)
            - "38" (Jeollanam-do)
            - "39" (Jeju-do)
        language (str, optional): Language for results (default: "en"). Supported:
            - "en" (English)
            - "jp" (Japanese)
            - "zh-cn" (Simplified Chinese)
            - "zh-tw" (Traditional Chinese)
            - "de" (German)
            - "fr" (French)
            - "es" (Spanish)
            - "ru" (Russian)
        page (int, optional): Page number for pagination (default: 1, min: 1)
        rows (int, optional): Number of items per page (default: 20, max: 100)
        filter (list[str], optional): List of keys to include in each result item (whitelist).
            - If filter is None or an empty list ([]), all fields are returned.
            - If filter contains values, only the specified keys will be included in each item, and all other keys will be removed.

    Returns:
        dict: Search results with structure:
        {
            "total_count": int,     # Total number of matching items
            "num_of_rows": int,     # Number of items per page
            "page_no": int,         # Current page number
            "items": [              # List of tourism items
                {
                    "title": str,           # Name of the attraction/place
                    "addr1": str,           # Primary address
                    "addr2": str,           # Secondary address
                    "areacode": str,        # Area code
                    "sigungucode": str,     # Sigungu code
                    "cat1": str,            # Category 1 code
                    "cat2": str,            # Category 2 code
                    "cat3": str,            # Category 3 code
                    "contentid": str,       # Unique content ID
                    "contenttypeid": str,   # Content type ID
                    "createdtime": str,     # Creation timestamp
                    "modifiedtime": str,    # Last modified timestamp
                    "tel": str,             # Phone number
                    "firstimage": str,      # URL of main image
                    "firstimage2": str,     # URL of thumbnail image
                    "mapx": str,            # Longitude
                    "mapy": str,            # Latitude
                    "mlevel": str,          # Map level
                    "cpyrhtDivCd": str      # Copyright division code
                }
                # ... more items
            ]
        }

    Example:
        search_tourism_by_keyword("Gyeongbokgung", "Tourist Attraction", "1", "en", 1, 10)
    """
    # Get the API client lazily
    client = get_api_client()

    # Validate and convert content_type
    content_type_id = None
    if content_type:
        content_type_id = next(
            (
                k
                for k, v in CONTENTTYPE_ID_MAP.items()
                if v.lower() == content_type.lower()
            ),
            None,
        )
        if content_type_id is None:
            valid_types = ", ".join(CONTENTTYPE_ID_MAP.values())
            raise ValueError(
                f"Invalid content_type: '{content_type}'. Valid types are: {valid_types}"
            )

    # Call the API client and return dict directly
    result = await client.search_by_keyword(
        keyword=keyword,
        content_type_id=content_type_id,
        area_code=area_code,
        language=language,
        page=page,
        rows=rows,
    )
    if filter:
        # Apply additional filtering if provided
        filter_items = []
        for item in result.get("items", []):
            item = {k: v for k, v in item.items() if k in filter}
            filter_items.append(item)
        result["items"] = filter_items
    return result


@mcp.tool
async def get_tourism_by_area(
    area_code: str,
    sigungu_code: str | None = None,
    content_type: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
    filter: list[str] | None = None,
) -> dict:
    """
    Browse tourism information by geographic areas in Korea.

    This tool retrieves tourism items from a specific geographic area in Korea.
    It allows filtering by area code, sigungu (district) code, and content type
    to find relevant tourism information in a particular region.

    Args:
        area_code (str): Area code. Valid values:
            - "1" (Seoul)
            - "2" (Incheon)
            - "3" (Daejeon)
            - "4" (Daegu)
            - "5" (Gwangju)
            - "6" (Busan)
            - "7" (Ulsan)
            - "8" (Sejong)
            - "31" (Gyeonggi-do)
            - "32" (Gangwon-do)
            - "33" (Chungcheongbuk-do)
            - "34" (Chungcheongnam-do)
            - "35" (Gyeongsangbuk-do)
            - "36" (Gyeongsangnam-do)
            - "37" (Jeonbuk-do)
            - "38" (Jeollanam-do)
            - "39" (Jeju-do)
        sigungu_code (str, optional): Sigungu (district) code within the area
        content_type (str, optional): Type of content to filter. Valid values:
            - "Tourist Attraction" (default)
            - "Cultural Facility"
            - "Festival Event"
            - "Leisure Activity"
            - "Accommodation"
            - "Shopping"
            - "Restaurant"
            - "Transportation"
        language (str, optional): Language for results (default: "en"). Supported:
            - "en" (English)
            - "jp" (Japanese)
            - "zh-cn" (Simplified Chinese)
            - "zh-tw" (Traditional Chinese)
            - "de" (German)
            - "fr" (French)
            - "es" (Spanish)
            - "ru" (Russian)
        page (int, optional): Page number for pagination (default: 1, min: 1)
        rows (int, optional): Number of items per page (default: 20, max: 100)
        filter (list[str], optional): List of keys to include in each result item (whitelist).
            - If filter is None or an empty list ([]), all fields are returned.
            - If filter contains values, only the specified keys will be included in each item, and all other keys will be removed.

    Returns:
        dict: Area-based tourism information with structure:
        {
            "total_count": int,     # Total number of matching items
            "num_of_rows": int,     # Number of items per page
            "page_no": int,         # Current page number
            "items": [              # List of tourism items
                {
                    "title": str,           # Name of the attraction/place
                    "addr1": str,           # Primary address
                    "addr2": str,           # Secondary address
                    "areacode": str,        # Area code
                    "sigungucode": str,     # Sigungu code
                    "cat1": str,            # Category 1 code
                    "cat2": str,            # Category 2 code
                    "cat3": str,            # Category 3 code
                    "contentid": str,       # Unique content ID
                    "contenttypeid": str,   # Content type ID
                    "createdtime": str,     # Creation timestamp
                    "modifiedtime": str,    # Last modified timestamp
                    "tel": str,             # Phone number
                    "firstimage": str,      # URL of main image
                    "firstimage2": str,     # URL of thumbnail image
                    "mapx": str,            # Longitude
                    "mapy": str,            # Latitude
                    "zipcode": str,         # Postal code
                    "mlevel": str           # Map level
                }
                # ... more items
            ]
        }

    Example:
        get_tourism_by_area("1", "1", "Tourist Attraction", "en", 1, 20)
    """
    # Validate and convert content_type
    content_type_id = None
    if content_type:
        content_type_id = next(
            (
                k
                for k, v in CONTENTTYPE_ID_MAP.items()
                if v.lower() == content_type.lower()
            ),
            None,
        )
        if content_type_id is None:
            valid_types = ", ".join(CONTENTTYPE_ID_MAP.values())
            raise ValueError(
                f"Invalid content_type: '{content_type}'. Valid types are: {valid_types}"
            )

    # Call the API client and return dict directly
    result = await get_api_client().get_area_based_list(
        area_code=area_code,
        sigunguCode=sigungu_code,
        content_type_id=content_type_id,
        language=language,
        page=page,
        rows=rows,
    )
    if filter:
        # Apply additional filtering if provided
        filter_items = []
        for item in result.get("items", []):
            item = {k: v for k, v in item.items() if k in filter}
            filter_items.append(item)
        result["items"] = filter_items
    return result


@mcp.tool
async def find_nearby_attractions(
    longitude: float,
    latitude: float,
    radius: int = 1000,
    content_type: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
    filter: list[str] | None = None,
) -> dict:
    """
    Find tourism attractions near a specific location in Korea.

    This tool performs a location-based search to find tourism items within a specified
    radius of given GPS coordinates. It's useful for finding nearby attractions,
    restaurants, or other tourism facilities when you know a specific location.

    Args:
        longitude (float): Longitude coordinate (e.g., 126.9780 for Seoul)
        latitude (float): Latitude coordinate (e.g., 37.5665 for Seoul)
        radius (int, optional): Search radius in meters (default: 1000, max: 20000)
        content_type (str, optional): Type of content to filter. Valid values:
            - "Tourist Attraction" (default)
            - "Cultural Facility"
            - "Festival Event"
            - "Leisure Activity"
            - "Accommodation"
            - "Shopping"
            - "Restaurant"
            - "Transportation"
        language (str, optional): Language for results (default: "en"). Supported:
            - "en" (English)
            - "jp" (Japanese)
            - "zh-cn" (Simplified Chinese)
            - "zh-tw" (Traditional Chinese)
            - "de" (German)
            - "fr" (French)
            - "es" (Spanish)
            - "ru" (Russian)
        page (int, optional): Page number for pagination (default: 1, min: 1)
        rows (int, optional): Number of items per page (default: 20, max: 100)
        filter (list[str], optional): List of keys to include in each result item (whitelist).
            - If filter is None or an empty list ([]), all fields are returned.
            - If filter contains values, only the specified keys will be included in each item, and all other keys will be removed.

    Returns:
        dict: Nearby tourism attractions with structure:
        {
            "total_count": int,     # Total number of matching items
            "num_of_rows": int,     # Number of items per page
            "page_no": int,         # Current page number
            "search_radius": int,   # Search radius used
            "items": [              # List of tourism items
                {
                    "title": str,           # Name of the attraction/place
                    "addr1": str,           # Primary address
                    "addr2": str,           # Secondary address
                    "areacode": str,        # Area code
                    "sigungucode": str,     # Sigungu code
                    "cat1": str,            # Category 1 code
                    "cat2": str,            # Category 2 code
                    "cat3": str,            # Category 3 code
                    "contentid": str,       # Unique content ID
                    "contenttypeid": str,   # Content type ID
                    "createdtime": str,     # Creation timestamp
                    "modifiedtime": str,    # Last modified timestamp
                    "tel": str,             # Phone number
                    "firstimage": str,      # URL of main image
                    "firstimage2": str,     # URL of thumbnail image
                    "mapx": str,            # Longitude
                    "mapy": str,            # Latitude
                    "mlevel": str,          # Map level
                    "dist": str             # Distance from the specified coordinates
                }
                # ... more items
            ]
        }

    Example:
        find_nearby_attractions(126.9780, 37.5665, 1000, "Tourist Attraction", "en", 1, 10)
    """
    # Validate and convert content_type
    content_type_id = None
    if content_type:
        content_type_id = next(
            (
                k
                for k, v in CONTENTTYPE_ID_MAP.items()
                if v.lower() == content_type.lower()
            ),
            None,
        )
        if content_type_id is None:
            valid_types = ", ".join(CONTENTTYPE_ID_MAP.values())
            raise ValueError(
                f"Invalid content_type: '{content_type}'. Valid types are: {valid_types}"
            )

    # Call the API client and return dict directly
    results = await get_api_client().get_location_based_list(
        mapx=longitude,
        mapy=latitude,
        radius=radius,
        content_type_id=content_type_id,
        language=language,
        page=page,
        rows=rows,
    )
    # Apply filter if provided
    if filter:
        filter_items = []
        for item in results.get("items", []):
            item = {k: v for k, v in item.items() if k in filter}
            filter_items.append(item)
        results["items"] = filter_items
    # Add search radius to the results
    return {**results, "search_radius": radius}


@mcp.tool
async def search_festivals_by_date(
    start_date: str,
    end_date: str | None = None,
    area_code: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
    filter: list[str] | None = None,
) -> dict:
    """
    Find festivals in Korea by date range.

    This tool searches for festivals and events occurring within a specified date range.
    It's useful for finding cultural events, celebrations, and festivals happening
    during a particular period or ongoing events.

    Args:
        start_date (str): Start date in YYYYMMDD format (e.g., "20250501" for May 1, 2025)
        end_date (str, optional): End date in YYYYMMDD format (e.g., "20250531" for May 31, 2025)
            If not provided, searches for events starting from the start_date
        area_code (str, optional): Area code to filter results. Valid values:
            - "1" (Seoul)
            - "2" (Incheon)
            - "3" (Daejeon)
            - "4" (Daegu)
            - "5" (Gwangju)
            - "6" (Busan)
            - "7" (Ulsan)
            - "8" (Sejong)
            - "31" (Gyeonggi-do)
            - "32" (Gangwon-do)
            - "33" (Chungcheongbuk-do)
            - "34" (Chungcheongnam-do)
            - "35" (Gyeongsangbuk-do)
            - "36" (Gyeongsangnam-do)
            - "37" (Jeonbuk-do)
            - "38" (Jeollanam-do)
            - "39" (Jeju-do)
        language (str, optional): Language for results (default: "en"). Supported:
            - "en" (English)
            - "jp" (Japanese)
            - "zh-cn" (Simplified Chinese)
            - "zh-tw" (Traditional Chinese)
            - "de" (German)
            - "fr" (French)
            - "es" (Spanish)
            - "ru" (Russian)
        page (int, optional): Page number for pagination (default: 1, min: 1)
        rows (int, optional): Number of items per page (default: 20, max: 100)
        filter (list[str], optional): List of keys to include in each result item (whitelist).
            - If filter is None or an empty list ([]), all fields are returned.
            - If filter contains values, only the specified keys will be included in each item, and all other keys will be removed.

    Returns:
        dict: Festivals within the specified date range with structure:
        {
            "total_count": int,     # Total number of matching items
            "num_of_rows": int,     # Number of items per page
            "page_no": int,         # Current page number
            "start_date": str,      # Search start date
            "end_date": str,        # Search end date or "ongoing"
            "items": [              # List of festival items
                {
                    "title": str,           # Name of the festival
                    "addr1": str,           # Primary address
                    "addr2": str,           # Secondary address
                    "areacode": str,        # Area code
                    "contentid": str,       # Unique content ID
                    "contenttypeid": str,   # Content type ID
                    "createdtime": str,     # Creation timestamp
                    "eventstartdate": str,  # Festival start date
                    "eventenddate": str,    # Festival end date
                    "firstimage": str,      # URL of main image
                    "firstimage2": str,     # URL of thumbnail image
                    "mapx": str,            # Longitude
                    "mapy": str,            # Latitude
                    "mlevel": str,          # Map level
                    "tel": str,             # Phone number
                    "cat1": str,            # Category 1 code
                    "cat2": str,            # Category 2 code
                    "cat3": str             # Category 3 code
                }
                # ... more items
            ]
        }

    Example:
        search_festivals_by_date("20250501", "20250531", "1", "en", 1, 20)
    """
    # Call the API client and return dict directly
    results = await get_api_client().search_festival(
        event_start_date=start_date,
        event_end_date=end_date,
        area_code=area_code,
        language=language,
        page=page,
        rows=rows,
    )
    # Apply filter if provided
    if filter:
        filter_items = []
        for item in results.get("items", []):
            item = {k: v for k, v in item.items() if k in filter}
            filter_items.append(item)
        results["items"] = filter_items
    # Add date information to the results
    return {
        **results,
        "start_date": start_date,
        "end_date": end_date or "ongoing",
    }


@mcp.tool
async def find_accommodations(
    area_code: str | None = None,
    sigungu_code: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
    filter: list[str] | None = None,
) -> dict:
    """
    Find accommodations in Korea by area.

    This tool searches for accommodation options (hotels, guesthouses, pensions, etc.)
    in a specific area in Korea. It provides detailed information about lodging
    facilities including location, contact information, and special certifications.

    Args:
        area_code (str, optional): Area code. Valid values:
            - "1" (Seoul)
            - "2" (Incheon)
            - "3" (Daejeon)
            - "4" (Daegu)
            - "5" (Gwangju)
            - "6" (Busan)
            - "7" (Ulsan)
            - "8" (Sejong)
            - "31" (Gyeonggi-do)
            - "32" (Gangwon-do)
            - "33" (Chungcheongbuk-do)
            - "34" (Chungcheongnam-do)
            - "35" (Gyeongsangbuk-do)
            - "36" (Gyeongsangnam-do)
            - "37" (Jeonbuk-do)
            - "38" (Jeollanam-do)
            - "39" (Jeju-do)
        sigungu_code (str, optional): Sigungu (district) code within the area
        language (str, optional): Language for results (default: "en"). Supported:
            - "en" (English)
            - "jp" (Japanese)
            - "zh-cn" (Simplified Chinese)
            - "zh-tw" (Traditional Chinese)
            - "de" (German)
            - "fr" (French)
            - "es" (Spanish)
            - "ru" (Russian)
        page (int, optional): Page number for pagination (default: 1, min: 1)
        rows (int, optional): Number of items per page (default: 20, max: 100)
        filter (list[str], optional): List of keys to include in each result item (whitelist).
            - If filter is None or an empty list ([]), all fields are returned.
            - If filter contains values, only the specified keys will be included in each item, and all other keys will be removed.

    Returns:
        dict: Accommodation options with structure:
        {
            "total_count": int,     # Total number of matching items
            "num_of_rows": int,     # Number of items per page
            "page_no": int,         # Current page number
            "items": [              # List of accommodation items
                {
                    "title": str,           # Name of the accommodation
                    "addr1": str,           # Primary address
                    "addr2": str,           # Secondary address
                    "areacode": str,        # Area code
                    "sigungucode": str,     # Sigungu code
                    "contentid": str,       # Unique content ID
                    "contenttypeid": str,   # Content type ID
                    "createdtime": str,     # Creation timestamp
                    "firstimage": str,      # URL of main image
                    "firstimage2": str,     # URL of thumbnail image
                    "mapx": str,            # Longitude
                    "mapy": str,            # Latitude
                    "mlevel": str,          # Map level
                    "tel": str,             # Phone number
                    "cat1": str,            # Category 1 code
                    "cat2": str,            # Category 2 code
                    "cat3": str,            # Category 3 code
                    "hanok": str,           # Korean traditional house flag
                    "benikia": str,         # Benikia hotel flag
                    "goodstay": str         # Goodstay accommodation flag
                }
                # ... more items
            ]
        }

    Example:
        find_accommodations("1", "1", "en", 1, 20)
    """
    # Call the API client and return dict directly
    result = await get_api_client().search_stay(
        area_code=area_code,
        sigungu_code=sigungu_code,
        language=language,
        page=page,
        rows=rows,
    )
    if filter:
        filter_items = []
        for item in result.get("items", []):
            item = {k: v for k, v in item.items() if k in filter}
            filter_items.append(item)
        result["items"] = filter_items
    return result


@mcp.tool
async def get_detailed_information(
    content_id: str,
    content_type: str | None = None,
    language: str | None = None,
) -> dict:
    """
    Get detailed information about a specific tourism item in Korea.

    This tool retrieves comprehensive details about a specific tourism item by its
    content ID. It combines common information, introduction details, and additional
    information to provide a complete picture of the tourism item.

    Args:
        content_id (str): Content ID of the tourism item (obtained from other search functions)
        content_type (str, optional): Type of content. Valid values:
            - "Tourist Attraction"
            - "Cultural Facility"
            - "Festival Event"
            - "Leisure Activity"
            - "Accommodation"
            - "Shopping"
            - "Restaurant"
            - "Transportation"
        language (str, optional): Language for results (default: "en"). Supported:
            - "en" (English)
            - "jp" (Japanese)
            - "zh-cn" (Simplified Chinese)
            - "zh-tw" (Traditional Chinese)
            - "de" (German)
            - "fr" (French)
            - "es" (Spanish)
            - "ru" (Russian)

    Returns:
        dict: Detailed information with structure:
        {
            # Common information
            "title": str,           # Name of the item
            "contentid": str,       # Unique content ID
            "contenttypeid": str,   # Content type ID
            "addr1": str,           # Primary address
            "addr2": str,           # Secondary address
            "areacode": str,        # Area code
            "sigungucode": str,     # Sigungu code
            "cat1": str,            # Category 1 code
            "cat2": str,            # Category 2 code
            "cat3": str,            # Category 3 code
            "mapx": str,            # Longitude
            "mapy": str,            # Latitude
            "mlevel": str,          # Map level
            "overview": str,        # Detailed description
            "tel": str,             # Phone number
            "telname": str,         # Contact name
            "homepage": str,        # Website URL
            "firstimage": str,      # URL of main image
            "firstimage2": str,     # URL of thumbnail image
            "createdtime": str,     # Creation timestamp
            "modifiedtime": str,    # Last modified timestamp
            "zipcode": str,         # Postal code

            # Introduction details (varies by content type)
            "infocenter": str,      # Information center (for attractions)
            "restdate": str,        # Rest/closing days
            "usetime": str,         # Hours of operation
            "parking": str,         # Parking information
            # ... other type-specific fields

            # Additional information
            "additional_info": [    # List of additional details
                {
                    "infoname": str,    # Name of the information
                    "infotext": str,    # Detailed text information
                    "fldgubun": str,    # Field division code
                    "serialnum": str    # Serial number
                }
                # ... more items
            ]
        }

    Example:
        get_detailed_information("126508", "Tourist Attraction", "en")
    """
    # Validate and convert content_type
    content_type_id = None
    if content_type:
        content_type_id = next(
            (
                k
                for k, v in CONTENTTYPE_ID_MAP.items()
                if v.lower() == content_type.lower()
            ),
            None,
        )
        if content_type_id is None:
            valid_types = ", ".join(CONTENTTYPE_ID_MAP.values())
            raise ValueError(
                f"Invalid content_type: '{content_type}'. Valid types are: {valid_types}"
            )

    # Get common details
    common_details = await get_api_client().get_detail_common(
        content_id=content_id,
        content_type_id=content_type_id,
        language=language,
        overview_yn="Y",
        first_image_yn="Y",
        mapinfo_yn="Y",
    )

    # Get intro details if content_type_id is provided
    intro_details: Dict[str, Any] = {}
    if content_type_id:
        intro_result = await get_api_client().get_detail_intro(
            content_id=content_id, content_type_id=content_type_id, language=language
        )
        intro_details = (
            intro_result.get("items", [{}])[0] if intro_result.get("items") else {}
        )

    # Get additional details
    additional_details: Dict[str, Any] = {}
    if content_type_id:
        additional_result = await get_api_client().get_detail_info(
            content_id=content_id, content_type_id=content_type_id, language=language
        )
        additional_details = {"additional_info": additional_result.get("items", [])}

    # Combine all details
    item = common_details.get("items", [{}])[0] if common_details.get("items") else {}
    return {**item, **intro_details, **additional_details}


@mcp.tool
async def get_tourism_images(
    content_id: str,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
) -> dict:
    """
    Get images for a specific tourism item in Korea.

    This tool retrieves all available images for a specific tourism item by its
    content ID. It provides both original and thumbnail image URLs along with
    image metadata.

    Args:
        content_id (str): Content ID of the tourism item (obtained from other search functions)
        language (str, optional): Language for results (default: "en"). Supported:
            - "en" (English)
            - "jp" (Japanese)
            - "zh-cn" (Simplified Chinese)
            - "zh-tw" (Traditional Chinese)
            - "de" (German)
            - "fr" (French)
            - "es" (Spanish)
            - "ru" (Russian)
        page (int, optional): Page number for pagination (default: 1, min: 1)
        rows (int, optional): Number of items per page (default: 20, max: 100)

    Returns:
        dict: Images with structure:
        {
            "total_count": int,     # Total number of matching items
            "content_id": str,      # Content ID this image belongs to
            "items": [              # List of image items
                {
                    "contentid": str,       # Content ID this image belongs to
                    "imgname": str,         # Image name
                    "originimgurl": str,    # URL of original image
                    "smallimageurl": str,   # URL of small/thumbnail image
                    "serialnum": str,       # Serial number
                    "cpyrhtDivCd": str      # Copyright division code
                }
                # ... more items
            ]
        }

    Example:
        get_tourism_images("126508", "en", 1, 10)
    """
    # Call the API client and return dict directly
    results = await get_api_client().get_detail_images(
        content_id=content_id, language=language, page=page, rows=rows
    )
    # Add content_id to the results
    return {**results, "content_id": content_id}


@mcp.tool
async def get_area_codes(
    parent_area_code: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 100,
) -> dict:
    """
    Get area codes for regions in Korea.

    This tool retrieves area codes and their corresponding names for Korean regions.
    It can be used to get top-level area codes (provinces/cities) or sub-area codes
    (districts/counties) within a specific area.

    Args:
        parent_area_code (str, optional): Parent area code to get sub-areas
            - If None: Returns top-level area codes (provinces/cities)
            - If provided: Returns sigungu codes for that area
        language (str, optional): Language for results (default: "en"). Supported:
            - "en" (English)
            - "jp" (Japanese)
            - "zh-cn" (Simplified Chinese)
            - "zh-tw" (Traditional Chinese)
            - "de" (German)
            - "fr" (French)
            - "es" (Spanish)
            - "ru" (Russian)
        page (int, optional): Page number for pagination (default: 1, min: 1)
        rows (int, optional): Number of items per page (default: 100, max: 100)

    Returns:
        dict: Area codes with structure:
        {
            "total_count": int,     # Total number of matching items
            "parent_area_code": str, # Parent area code used (or null)
            "items": [              # List of area code items
                {
                    "code": str,            # Area code value
                    "name": str,            # Area name
                    "rnum": str             # Row number
                }
                # ... more items
            ]
        }

    Available area codes:
        - "1" (Seoul)
        - "2" (Incheon)
        - "3" (Daejeon)
        - "4" (Daegu)
        - "5" (Gwangju)
        - "6" (Busan)
        - "7" (Ulsan)
        - "8" (Sejong)
        - "31" (Gyeonggi-do)
        - "32" (Gangwon-do)
        - "33" (Chungcheongbuk-do)
        - "34" (Chungcheongnam-do)
        - "35" (Gyeongsangbuk-do)
        - "36" (Gyeongsangnam-do)
        - "37" (Jeonbuk-do)
        - "38" (Jeollanam-do)
        - "39" (Jeju-do)

    Example:
        get_area_codes(None, "en", 1, 50)  # Get top-level areas
        get_area_codes("1", "en", 1, 50)   # Get districts in Seoul
    """
    # Call the API client and return dict directly
    results = await get_api_client().get_area_code_list(
        area_code=parent_area_code, language=language, page=page, rows=rows
    )
    # Add parent_area_code to the results
    return {**results, "parent_area_code": parent_area_code}


# Add health check endpoint for HTTP transports
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """
    Health check endpoint for HTTP transports.

    This endpoint provides a simple health check for the MCP server when running
    in HTTP mode. It verifies that the server is running and the API client is
    properly configured.

    Returns:
        JSONResponse: Health status with server information
    """
    try:
        # Try to get the API client to verify it's properly configured
        _ = get_api_client()
        return JSONResponse(
            {
                "status": "healthy",
                "service": "Korea Tourism API MCP Server",
                "transport": os.environ.get("MCP_TRANSPORT", "stdio"),
                "timestamp": asyncio.get_event_loop().time(),
            }
        )
    except Exception as e:
        return JSONResponse(
            {
                "status": "unhealthy",
                "service": "Korea Tourism API MCP Server",
                "error": str(e),
                "transport": os.environ.get("MCP_TRANSPORT", "stdio"),
                "timestamp": asyncio.get_event_loop().time(),
            },
            status_code=503,
        )


def parse_server_config(args: list[str] | None = None) -> tuple[str, dict[str, Any]]:
    """
    Parse server configuration from command line arguments and environment variables.

    Args:
        args: Command line arguments list. If None, uses sys.argv.

    Returns:
        Tuple of (transport, http_config) where:
        - transport: The selected transport protocol
        - http_config: Dictionary of HTTP configuration options (empty for stdio)
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Korea Tourism API MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default=None,
        help="Transport protocol to use (default: from environment or stdio)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host address for HTTP transports (default: from environment or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for HTTP transports (default: from environment or 8000)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Log level for the server (default: from environment or INFO)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path for HTTP endpoints (default: from environment or /mcp)",
    )

    parsed_args = parser.parse_args(args)

    # Determine transport and configuration from args or environment variables
    transport = parsed_args.transport or os.environ.get("MCP_TRANSPORT", "stdio")

    # Configuration for HTTP transports
    http_config = {}
    if transport in ["streamable-http", "sse"]:
        http_config.update(
            {
                "host": parsed_args.host or os.environ.get("MCP_HOST", "127.0.0.1"),
                "port": parsed_args.port
                if parsed_args.port is not None
                else int(os.environ.get("MCP_PORT", "8000")),
                "log_level": parsed_args.log_level
                or os.environ.get("MCP_LOG_LEVEL", "INFO"),
                "path": parsed_args.path or os.environ.get("MCP_PATH", "/mcp"),
            }
        )

    return transport, http_config


def run_server(transport: str, http_config: dict[str, Any]) -> None:
    """
    Run the MCP server with the given configuration.

    Args:
        transport: Transport protocol to use
        http_config: HTTP configuration dictionary
    """
    # Log the configuration
    logger.info(f"Starting Korea Tourism API MCP Server with transport: {transport}")
    if http_config:
        logger.info(f"HTTP Configuration: {http_config}")

    try:
        # Run with the selected transport
        if transport == "stdio":
            logger.info("Using stdio transport - connect via MCP client")
            mcp.run(transport="stdio")
        elif transport in ["streamable-http", "sse"]:
            logger.info(
                f"Using {transport} transport on http://{http_config['host']}:{http_config['port']}{http_config['path']}"
            )
            mcp.run(transport=transport, **http_config)
        else:
            logger.error(f"Unknown transport: {transport}")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    transport, http_config = parse_server_config()
    run_server(transport, http_config)
