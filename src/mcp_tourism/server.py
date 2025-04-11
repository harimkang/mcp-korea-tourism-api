# server.py
import os
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from mcp_tourism.api_client import KoreaTourismApiClient, CONTENTTYPE_ID_MAP

# Create an MCP server
mcp = FastMCP(
    name="Korea Tourism API",
    description="API for Korea Tourism information",
    version="0.1",
    dependencies=["httpx", "cachetools", "tenacity", "ratelimit"],
)

# Lazy initialization of the API client
_api_client: Optional[KoreaTourismApiClient] = None

def get_api_client() -> KoreaTourismApiClient:
    """
    Lazily initialize the API client only when needed.
    This function is called only when a tool is actually invoked.
    """
    global _api_client
    if _api_client is None:
        # Get API key from environment variable
        api_key = os.environ.get("KOREA_TOURISM_API_KEY")
        
        # Instead of raising an error immediately, log a warning and use a placeholder
        # The actual API calls will fail gracefully with proper error messages
        if not api_key:
            import logging
            logging.warning(
                "KOREA_TOURISM_API_KEY environment variable is not set. "
                "API calls will fail until a valid key is provided."
            )
            api_key = "missing_api_key"  # Placeholder that will cause API calls to fail properly
            
        # Initialize the client
        _api_client = KoreaTourismApiClient(api_key=api_key)
    return _api_client

# MCP Tools for Korea Tourism API

@mcp.tool()
async def search_tourism_by_keyword(
    keyword: str,
    content_type: str = None,
    area_code: str = None,
    language: str = None,
) -> Dict[str, Any]:
    """
    Search for tourism information in Korea by keyword.
    
    Args:
        keyword: Search keyword (e.g., "Gyeongbokgung", "Hanok", "Bibimbap")
        content_type: Type of content to search for (e.g., "Tourist Attraction", "Restaurant", "Festival Event")
        area_code: Area code to filter results (e.g., "1" for Seoul)
        language: Language for results (e.g., "en", "jp", "zh-cn"), default is "en"
        
    Returns:
        A dictionary containing search results with tourism information.
    """
    # Get the API client lazily
    client = get_api_client()
    
    # Convert human-readable content type to ID if provided
    content_type_id = None
    if content_type:
        content_type_id = next(
            (k for k, v in CONTENTTYPE_ID_MAP.items() if v.lower() == content_type.lower()),
            None
        )
    
    # Call the API client
    return await client.search_by_keyword(
        keyword=keyword,
        content_type_id=content_type_id,
        area_code=area_code,
        language=language
    )


@mcp.tool()
async def get_tourism_by_area(
    area_code: str,
    sigungu_code: str = None,
    content_type: str = None,
    language: str = None,
) -> Dict[str, Any]:
    """
    Browse tourism information by geographic areas in Korea.
    
    Args:
        area_code: Area code (e.g., "1" for Seoul)
        sigungu_code: Sigungu (district) code within the area
        content_type: Type of content to filter (e.g., "Tourist Attraction", "Restaurant")
        language: Language for results (e.g., "en", "jp", "zh-cn")
        
    Returns:
        A dictionary containing tourism information in the specified area.
    """
    # Convert human-readable content type to ID if provided
    content_type_id = None
    if content_type:
        content_type_id = next(
            (k for k, v in CONTENTTYPE_ID_MAP.items() if v.lower() == content_type.lower()),
            None
        )
    
    # Call the API client
    results = await get_api_client().get_area_based_list(
        area_code=area_code,
        sigunguCode=sigungu_code,
        content_type_id=content_type_id,
        language=language
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "page_no": results.get("page_no", 1),
        "num_of_rows": results.get("num_of_rows", 0)
    }

@mcp.tool()
async def find_nearby_attractions(
    longitude: float,
    latitude: float,
    radius: int = 1000,
    content_type: str = None,
    language: str = None,
) -> Dict[str, Any]:
    """
    Find tourism attractions near a specific location in Korea.
    
    Args:
        longitude: Longitude coordinate (e.g., 126.9780)
        latitude: Latitude coordinate (e.g., 37.5665)
        radius: Search radius in meters (default: 1000)
        content_type: Type of content to filter (e.g., "Tourist Attraction", "Restaurant")
        language: Language for results (e.g., "en", "jp", "zh-cn")
        
    Returns:
        A dictionary containing tourism attractions near the specified coordinates.
    """
    # Convert human-readable content type to ID if provided
    content_type_id = None
    if content_type:
        content_type_id = next(
            (k for k, v in CONTENTTYPE_ID_MAP.items() if v.lower() == content_type.lower()),
            None
        )
    
    # Call the API client
    results = await get_api_client().get_location_based_list(
        mapx=longitude,
        mapy=latitude,
        radius=radius,
        content_type_id=content_type_id,
        language=language
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "page_no": results.get("page_no", 1),
        "num_of_rows": results.get("num_of_rows", 0),
        "search_radius": radius
    }

@mcp.tool()
async def search_festivals_by_date(
    start_date: str,
    end_date: str = None,
    area_code: str = None,
    language: str = None,
) -> Dict[str, Any]:
    """
    Find festivals in Korea by date range.
    
    Args:
        start_date: Start date in YYYYMMDD format (e.g., "20250501")
        end_date: Optional end date in YYYYMMDD format (e.g., "20250531")
        area_code: Area code to filter results (e.g., "1" for Seoul)
        language: Language for results (e.g., "en", "jp", "zh-cn")
        
    Returns:
        A dictionary containing festivals occurring within the specified date range.
    """
    # Call the API client
    results = await get_api_client().search_festival(
        event_start_date=start_date,
        event_end_date=end_date,
        area_code=area_code,
        language=language
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "page_no": results.get("page_no", 1),
        "num_of_rows": results.get("num_of_rows", 0),
        "start_date": start_date,
        "end_date": end_date or "ongoing"
    }

@mcp.tool()
async def find_accommodations(
    area_code: str = None,
    sigungu_code: str = None,
    language: str = None,
) -> Dict[str, Any]:
    """
    Find accommodations in Korea by area.
    
    Args:
        area_code: Area code (e.g., "1" for Seoul)
        sigungu_code: Sigungu (district) code within the area
        language: Language for results (e.g., "en", "jp", "zh-cn")
        
    Returns:
        A dictionary containing accommodation options in the specified area.
    """
    # Call the API client
    results = await get_api_client().search_stay(
        area_code=area_code,
        sigungu_code=sigungu_code,
        language=language
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "page_no": results.get("page_no", 1),
        "num_of_rows": results.get("num_of_rows", 0)
    }

@mcp.tool()
async def get_detailed_information(
    content_id: str,
    content_type: str = None,
    language: str = None,
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
    # Convert human-readable content type to ID if provided
    content_type_id = None
    if content_type:
        content_type_id = next(
            (k for k, v in CONTENTTYPE_ID_MAP.items() if v.lower() == content_type.lower()),
            None
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

@mcp.tool()
async def get_tourism_images(
    content_id: str,
    language: str = None,
) -> Dict[str, Any]:
    """
    Get images for a specific tourism item in Korea.
    
    Args:
        content_id: Content ID of the tourism item
        language: Language for results (e.g., "en", "jp", "zh-cn")
        
    Returns:
        A dictionary containing images for the specified tourism item.
    """
    # Call the API client
    results = await get_api_client().get_detail_images(
        content_id=content_id,
        language=language
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "content_id": content_id
    }

@mcp.tool()
async def get_area_codes(
    parent_area_code: str = None,
    language: str = None,
) -> Dict[str, Any]:
    """
    Get area codes for regions in Korea.
    
    Args:
        parent_area_code: Parent area code to get sub-areas (None for top-level areas)
        language: Language for results (e.g., "en", "jp", "zh-cn")
        
    Returns:
        A dictionary containing area codes and names.
    """
    # Call the API client
    results = await get_api_client().get_area_code_list(
        area_code=parent_area_code,
        language=language
    )
    
    return {
        "total_count": results.get("total_count", 0),
        "items": results.get("items", []),
        "parent_area_code": parent_area_code
    }

if __name__ == "__main__":
    import sys
    import traceback
    import asyncio
    
    # To avoid issues with "unhandled errors in TaskGroup", wrap everything in try-except
    try:
        # Use FastMCP's run method which should already handle asyncio event loop
        # Just make sure to catch exceptions clearly
        try:
            mcp.run(transport="stdio")
        except Exception as e:
            print(f"Error during MCP execution: {e}", file=sys.stderr)
            traceback.print_exc()
            sys.exit(1)
    except Exception as e:
        print(f"Error during MCP server setup: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
