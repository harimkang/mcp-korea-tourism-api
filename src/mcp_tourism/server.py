# server.py
import os
from typing import Dict, Any, Optional
from fastmcp import FastMCP
from mcp_tourism.api_client import KoreaTourismApiClient, CONTENTTYPE_ID_MAP
import logging

# Create an MCP server
mcp = FastMCP(
    name="Korea Tourism API",
    description="API for Korea Tourism information",
    version="0.1.2",
    dependencies=["httpx", "cachetools", "tenacity", "ratelimit"],
)

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

# MCP Tools for Korea Tourism API

async def search_tourism_by_keyword(
    keyword: str,
    content_type: str | None = None,
    area_code: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
) -> Dict[str, Any]:
    """
    Search for tourism information in Korea by keyword.
    
    Args:
        keyword: Search keyword (e.g., "Gyeongbokgung", "Hanok", "Bibimbap")
        content_type: Type of content to search for (e.g., "Tourist Attraction", "Restaurant", "Festival Event")
        area_code: Area code to filter results (e.g., "1" for Seoul)
        language: Language for results (e.g., "en", "jp", "zh-cn"), default is "en"
        page: Page number for pagination (default: 1)
        rows: Number of items per page (default: 20)
        
    Returns:
        A dictionary containing search results with tourism information.
    """
    # Get the API client lazily
    client = get_api_client()
    
    # Validate and convert content_type
    content_type_id = None
    if content_type:
        content_type_id = next(
            (k for k, v in CONTENTTYPE_ID_MAP.items() if v.lower() == content_type.lower()),
            None
        )
        if content_type_id is None:
            valid_types = ", ".join(CONTENTTYPE_ID_MAP.values())
            raise ValueError(f"Invalid content_type: '{content_type}'. Valid types are: {valid_types}")
    
    # Call the API client
    return await client.search_by_keyword(
        keyword=keyword,
        content_type_id=content_type_id,
        area_code=area_code,
        language=language,
        page=page,
        rows=rows
    )


async def get_tourism_by_area(
    area_code: str,
    sigungu_code: str | None = None,
    content_type: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
) -> Dict[str, Any]:
    """
    Browse tourism information by geographic areas in Korea.
    
    Args:
        area_code: Area code (e.g., "1" for Seoul)
        sigungu_code: Sigungu (district) code within the area
        content_type: Type of content to filter (e.g., "Tourist Attraction", "Restaurant")
        language: Language for results (e.g., "en", "jp", "zh-cn")
        page: Page number for pagination (default: 1)
        rows: Number of items per page (default: 20)
        
    Returns:
        A dictionary containing tourism information in the specified area.
    """
    # Validate and convert content_type
    content_type_id = None
    if content_type:
        content_type_id = next(
            (k for k, v in CONTENTTYPE_ID_MAP.items() if v.lower() == content_type.lower()),
            None
        )
        if content_type_id is None:
            valid_types = ", ".join(CONTENTTYPE_ID_MAP.values())
            raise ValueError(f"Invalid content_type: '{content_type}'. Valid types are: {valid_types}")
    
    # Call the API client
    results = await get_api_client().get_area_based_list(
        area_code=area_code,
        sigunguCode=sigungu_code,
        content_type_id=content_type_id,
        language=language,
        page=page,
        rows=rows
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "page_no": results.get("page_no", 1),
        "num_of_rows": results.get("num_of_rows", 0)
    }

async def find_nearby_attractions(
    longitude: float,
    latitude: float,
    radius: int = 1000,
    content_type: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
) -> Dict[str, Any]:
    """
    Find tourism attractions near a specific location in Korea.
    
    Args:
        longitude: Longitude coordinate (e.g., 126.9780)
        latitude: Latitude coordinate (e.g., 37.5665)
        radius: Search radius in meters (default: 1000)
        content_type: Type of content to filter (e.g., "Tourist Attraction", "Restaurant")
        language: Language for results (e.g., "en", "jp", "zh-cn")
        page: Page number for pagination (default: 1)
        rows: Number of items per page (default: 20)
        
    Returns:
        A dictionary containing tourism attractions near the specified coordinates.
    """
    # Validate and convert content_type
    content_type_id = None
    if content_type:
        content_type_id = next(
            (k for k, v in CONTENTTYPE_ID_MAP.items() if v.lower() == content_type.lower()),
            None
        )
        if content_type_id is None:
            valid_types = ", ".join(CONTENTTYPE_ID_MAP.values())
            raise ValueError(f"Invalid content_type: '{content_type}'. Valid types are: {valid_types}")
    
    # Call the API client
    results = await get_api_client().get_location_based_list(
        mapx=longitude,
        mapy=latitude,
        radius=radius,
        content_type_id=content_type_id,
        language=language,
        page=page,
        rows=rows
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "page_no": results.get("page_no", 1),
        "num_of_rows": results.get("num_of_rows", 0),
        "search_radius": radius
    }

async def search_festivals_by_date(
    start_date: str,
    end_date: str | None = None,
    area_code: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
) -> Dict[str, Any]:
    """
    Find festivals in Korea by date range.
    
    Args:
        start_date: Start date in YYYYMMDD format (e.g., "20250501")
        end_date: Optional end date in YYYYMMDD format (e.g., "20250531")
        area_code: Area code to filter results (e.g., "1" for Seoul)
        language: Language for results (e.g., "en", "jp", "zh-cn")
        page: Page number for pagination (default: 1)
        rows: Number of items per page (default: 20)
        
    Returns:
        A dictionary containing festivals occurring within the specified date range.
    """
    # Call the API client
    results = await get_api_client().search_festival(
        event_start_date=start_date,
        event_end_date=end_date,
        area_code=area_code,
        language=language,
        page=page,
        rows=rows
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "page_no": results.get("page_no", 1),
        "num_of_rows": results.get("num_of_rows", 0),
        "start_date": start_date,
        "end_date": end_date or "ongoing"
    }

async def find_accommodations(
    area_code: str | None = None,
    sigungu_code: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
) -> Dict[str, Any]:
    """
    Find accommodations in Korea by area.
    
    Args:
        area_code: Area code (e.g., "1" for Seoul)
        sigungu_code: Sigungu (district) code within the area
        language: Language for results (e.g., "en", "jp", "zh-cn")
        page: Page number for pagination (default: 1)
        rows: Number of items per page (default: 20)
        
    Returns:
        A dictionary containing accommodation options in the specified area.
    """
    # Call the API client
    results = await get_api_client().search_stay(
        area_code=area_code,
        sigungu_code=sigungu_code,
        language=language,
        page=page,
        rows=rows
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "page_no": results.get("page_no", 1),
        "num_of_rows": results.get("num_of_rows", 0)
    }

async def get_detailed_information(
    content_id: str,
    content_type: str | None = None,
    language: str | None = None,
) -> Dict[str, Any]:
    """
    Get detailed information about a specific tourism item in Korea.
    
    Args:
        content_id: Content ID of the tourism item
        content_type: Type of content (e.g., "Tourist Attraction", "Restaurant")
        language: Language for results (e.g., "en", "jp", "zh-cn")
        
    Returns:
        A dictionary containing detailed information about the specified tourism item.
    """
    # Validate and convert content_type
    content_type_id = None
    if content_type:
        content_type_id = next(
            (k for k, v in CONTENTTYPE_ID_MAP.items() if v.lower() == content_type.lower()),
            None
        )
        if content_type_id is None:
            valid_types = ", ".join(CONTENTTYPE_ID_MAP.values())
            raise ValueError(f"Invalid content_type: '{content_type}'. Valid types are: {valid_types}")
    
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
            content_id=content_id,
            content_type_id=content_type_id,
            language=language
        )
        intro_details = intro_result.get("items", [{}])[0] if intro_result.get("items") else {}
    
    # Get additional details
    additional_details: Dict[str, Any] = {}
    if content_type_id:
        additional_result = await get_api_client().get_detail_info(
            content_id=content_id,
            content_type_id=content_type_id,
            language=language
        )
        additional_details = {"additional_info": additional_result.get("items", [])}
    
    # Combine all details
    item = common_details.get("items", [{}])[0] if common_details.get("items") else {}
    return {
        **item,
        **intro_details,
        **additional_details
    }

async def get_tourism_images(
    content_id: str,
    language: str | None = None,
    page: int = 1,
    rows: int = 20,
) -> Dict[str, Any]:
    """
    Get images for a specific tourism item in Korea.
    
    Args:
        content_id: Content ID of the tourism item
        language: Language for results (e.g., "en", "jp", "zh-cn")
        page: Page number for pagination (default: 1)
        rows: Number of items per page (default: 20)
        
    Returns:
        A dictionary containing images for the specified tourism item.
    """
    # Call the API client
    results = await get_api_client().get_detail_images(
        content_id=content_id,
        language=language,
        page=page,
        rows=rows
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "content_id": content_id
    }

async def get_area_codes(
    parent_area_code: str | None = None,
    language: str | None = None,
    page: int = 1,
    rows: int = 100,
) -> Dict[str, Any]:
    """
    Get area codes for regions in Korea.
    
    Args:
        parent_area_code: Parent area code to get sub-areas (None for top-level areas)
        language: Language for results (e.g., "en", "jp", "zh-cn")
        page: Page number for pagination (default: 1)
        rows: Number of items per page (default: 100)
        
    Returns:
        A dictionary containing area codes and names.
    """
    # Call the API client
    results = await get_api_client().get_area_code_list(
        area_code=parent_area_code,
        language=language,
        page=page,
        rows=rows
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "parent_area_code": parent_area_code
    }

# Register functions as MCP tools
mcp.tool(search_tourism_by_keyword)
mcp.tool(get_tourism_by_area)
mcp.tool(find_nearby_attractions)
mcp.tool(search_festivals_by_date)
mcp.tool(find_accommodations)
mcp.tool(get_detailed_information)
mcp.tool(get_tourism_images)
mcp.tool(get_area_codes)

if __name__ == "__main__":
    # Use FastMCP's simplified run method
    mcp.run()
