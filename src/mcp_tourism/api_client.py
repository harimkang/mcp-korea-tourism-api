import httpx
import logging
import asyncio
import urllib
import json
from typing import Dict, Optional, Any, Literal, ClassVar
from cachetools import TTLCache
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ratelimit import limits, sleep_and_retry


# Map of content type IDs to their human-readable names
CONTENTTYPE_ID_MAP = {
    "76": "Tourist Attraction",
    "78": "Cultural Facility",
    "85": "Festival Event",
    "75": "Leisure Activity",
    "80": "Accommodation",
    "79": "Shopping",
    "82": "Restaurant",
    "77": "Transportation",
}

# Map of supported languages to their service endpoints
LANGUAGE_SERVICE_MAP = {
    "en": "EngService1",   # English
    "jp": "JpnService1",   # Japanese
    "zh-cn": "ChsService1", # Simplified Chinese
    "zh-tw": "ChtService1", # Traditional Chinese
    "de": "GerService1",   # German
    "fr": "FreService1",   # French
    "es": "SpnService1",   # Spanish
    "ru": "RusService1",   # Russian
}

class TourismApiError(Exception):
    """Base exception for Tourism API errors"""
    pass

class TourismApiConnectionError(TourismApiError):
    """Connection error with Tourism API"""
    pass

class TourismApiClientError(TourismApiError):
    """Client-side error with Tourism API requests"""
    pass

class TourismApiServerError(TourismApiError):
    """Server-side error with Tourism API operations"""
    pass

class KoreaTourismApiClient:
    """
    Client for the Korea Tourism Organization API with caching and rate limiting.
    
    Features:
    - Multi-language support
    - Response caching with TTL
    - Rate limiting to respect API quotas
    - Automatic retries for transient errors
    - Connection pooling
    """
    
    # Base URL for all services
    BASE_URL = "http://apis.data.go.kr/B551011"
    
    # Common endpoints (will be prefixed with service name)
    AREA_BASED_LIST_ENDPOINT = "/areaBasedList1"
    LOCATION_BASED_LIST_ENDPOINT = "/locationBasedList1"
    SEARCH_KEYWORD_ENDPOINT = "/searchKeyword1"
    SEARCH_FESTIVAL_ENDPOINT = "/searchFestival1"
    SEARCH_STAY_ENDPOINT = "/searchStay1"
    DETAIL_COMMON_ENDPOINT = "/detailCommon1"
    DETAIL_INTRO_ENDPOINT = "/detailIntro1"
    DETAIL_INFO_ENDPOINT = "/detailInfo1"
    DETAIL_IMAGE_ENDPOINT = "/detailImage1"
    AREA_BASED_SYNC_LIST_ENDPOINT = "/areaBasedSyncList1"
    AREA_CODE_LIST_ENDPOINT = "/areaCode1"
    CATEGORY_CODE_LIST_ENDPOINT = "/categoryCode1"
    
    # Class-level connection pool and semaphore for concurrency control
    _shared_client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _request_semaphore: ClassVar[asyncio.Semaphore] = asyncio.Semaphore(10)  # Limit to 10 concurrent requests
    
    def __init__(self, api_key: str, language: str = "en"):
        """
        Initialize with optional language configuration.
        
        Args:
            language: Language code for content (en, ko, jp, zh, zh-cn, zh-tw, de, fr, es, ru)
        """
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("Korean Tourism API key must be provided in settings")
            
        self.logger = logging.getLogger("tourism_api_client")
            
        # Set language service
        self.language = language.lower()
        if self.language not in LANGUAGE_SERVICE_MAP:
            self.logger.warning(f"Unsupported language: {language}. Falling back to English.")
            self.language = "en"
            
        self.service_name = LANGUAGE_SERVICE_MAP[self.language]
        self.full_base_url = f"{self.BASE_URL}/{self.service_name}"
        
        # Cache setup - Cache responses for 24 hours by default
        self.cache = TTLCache(maxsize=1000, ttl=86400)  
        
    @classmethod
    async def get_shared_client(cls) -> httpx.AsyncClient:
        """Get or create the shared HTTP client with connection pooling"""
        async with cls._client_lock:
            if cls._shared_client is None:
                cls._shared_client = httpx.AsyncClient(
                    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
                    timeout=httpx.Timeout(30.0)
                )
            return cls._shared_client
        
    @classmethod
    async def close_all_connections(cls):
        """Close the shared client connection - call this when your application is shutting down"""
        async with cls._client_lock:
            if cls._shared_client is not None:
                await cls._shared_client.aclose()
                cls._shared_client = None
    
    def _process_response_error(self, response: httpx.Response):
        """Process HTTP errors and raise appropriate exceptions"""
        # Check status code first for efficiency
        if response.status_code >= 400:
            status_code = response.status_code
            
            # Try to extract error message
            error_msg = f"Tourism API error: HTTP {status_code}"
            try:
                error_data = response.json()
                if isinstance(error_data, dict) and "error" in error_data:
                    error_msg = f"Tourism API error: {error_data['error']}"
            except Exception:
                pass
                
            # Map status code to exception type
            if status_code >= 400 and status_code < 500:
                raise TourismApiClientError(f"Client error: {error_msg}")
            else:
                raise TourismApiServerError(f"Server error: {error_msg}")
    
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate a unique cache key for an API request"""
        # Sort params to ensure consistent keys
        sorted_params = sorted(
            [(k, v) for k, v in params.items() if k != "MobileOS" and k != "MobileApp"]
        )
        # Include language in cache key
        param_str = f"lang={self.language}&" + "&".join([f"{k}={v}" for k, v in sorted_params])
        return f"{endpoint}?{param_str}"
    
    @sleep_and_retry
    @limits(calls=5, period=1)  # 5 calls per second
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ConnectError, TourismApiServerError)),
        reraise=True
    )
    async def _make_request(self, endpoint: str, params: Dict[str, Any], use_cache: bool = True) -> Dict[str, Any]:
        """Make a request to the API with caching and rate limiting"""
        # Check cache first if caching is enabled
        if use_cache:
            cache_key = self._get_cache_key(endpoint, params)
            cached_response = self.cache.get(cache_key)
            if cached_response:
                self.logger.debug(f"Cache hit for {cache_key}")
                return cached_response
        
        # Use concurrency semaphore to limit simultaneous requests
        async with self._request_semaphore:
            # Add common parameters
            full_params = {
                "MobileOS": "ETC",
                "MobileApp": "MobileApp",
                "numOfRows": "100",  # Default to 100 results per request
                "pageNo": "1",
                "_type": "json",  # Return JSON format
                **params
            }
            
            # The API key is already URL-encoded in the settings, so we add it separately
            # to avoid double-encoding
            serviceKey = self.api_key
            
            # Build the full URL with proper service
            url = f"{self.full_base_url}{endpoint}"
            
            client = await self.get_shared_client()
            
            # First, encode the parameters
            encoded_params = urllib.parse.urlencode(full_params)
            
            # Then append the already-encoded service key
            full_url = f"{url}?serviceKey={serviceKey}&{encoded_params}"
            
            self.logger.debug(f"Making request to URL: {full_url}")
            response = await client.get(full_url)
            
            self._process_response_error(response)
            
            # Parse the response with better error handling
            try:
                # Check if the response has content
                if not response.content or len(response.content.strip()) == 0:
                    self.logger.error("Empty response received from tourism API")
                    raise TourismApiError("Empty response received from tourism API")
                
                result = response.json()
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON response: {e}. Response content: {response.text[:200]}")
                raise TourismApiError(f"Invalid JSON response: {str(e)}")
            
            # Extract the items from the nested response structure
            try:
                response_header = result["response"]["header"]
                response_body = result["response"]["body"]
                
                result_code = response_header.get("resultCode")
                if result_code != "0000":
                    raise TourismApiError(f"API error: {response_header.get('resultMsg', 'Unknown error')}")
                
                total_count = response_body.get("totalCount", 0)
                items = []
                
                if total_count > 0:
                    items_container = response_body.get("items", {})
                    if "item" in items_container:
                        items = items_container["item"]
                        if not isinstance(items, list):
                            items = [items]  # Ensure items is a list even if there's only one result
                
                # Structure the results
                result_data = {
                    "total_count": total_count,
                    "num_of_rows": response_body.get("numOfRows", 0),
                    "page_no": response_body.get("pageNo", 1),
                    "items": items
                }
                
                # Cache the response if caching is enabled
                if use_cache:
                    cache_key = self._get_cache_key(endpoint, params)
                    self.cache[cache_key] = result_data
                
                return result_data
                
            except (KeyError, TypeError) as e:
                self.logger.error(f"Error parsing Tourism API response: {e}")
                raise TourismApiError(f"Failed to parse API response: {e}")

    
    async def search_by_keyword(
        self,
        keyword: str,
        content_type_id: Optional[str] = None,
        area_code: Optional[str] = None,
        sigungu_code: Optional[str] = None,
        cat1: Optional[str] = None,
        cat2: Optional[str] = None,
        cat3: Optional[str] = None,
        language: Optional[str] = None,
        page: int = 1,
        rows: int = 20
    ) -> Dict[str, Any]:
        """
        Search tourism information by keyword.
        /searchKeyword1
        
        Args:
            keyword: Search keyword
            content_type_id: Content type ID to filter results
            area_code: Area code to filter results
            sigungu_code: Sigungu code to filter results, areaCode is required
            cat1: Major category code
            cat2: Middle category code (requires cat1)
            cat3: Minor category code (requires cat1 and cat2)
            language: Override the client's default language
            page: Page number for pagination
            rows: Number of items per page
            
        Returns:
            Dictionary containing search results with structure:
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
                    },
                    # ... more items
                ]
            }
        """
        params: Dict[str, Any] = {
            "keyword": keyword,  # Required by the API
            "arrange": "Q",  # Sort by {A: alphabetically, C: modified date, D: created date, O: alphabetically with image, Q: modified date with image, R: created date with image}
            "listYN": "Y",   # Return as a list
            "contentTypeId": content_type_id or "",
            "pageNo": str(page),
            "numOfRows": str(rows),
        }

        if area_code:
            params["areaCode"] = area_code

            if sigungu_code:
                params["sigunguCode"] = sigungu_code
        
        if cat1:
            params["cat1"] = cat1

            if cat2:
                params["cat2"] = cat2

                if cat3:
                    params["cat3"] = cat3
        
        # If a specific language is requested, create a new client with that language
        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.SEARCH_KEYWORD_ENDPOINT, params)
        
        # Otherwise use the current client's language
        return await self._make_request(self.SEARCH_KEYWORD_ENDPOINT, params)
    
    async def get_area_based_list(
        self,
        area_code: Optional[str] = None,
        content_type_id: Optional[str] = None,
        sigunguCode: Optional[str] = None,
        cat1: Optional[str] = None,
        cat2: Optional[str] = None,
        cat3: Optional[str] = None,
        language: Optional[str] = None,
        page: int = 1,
        rows: int = 20,
    ) -> Dict[str, Any]:
        """
        Get a list of tourism information by area.
        
        Args:
            area_code: Area code to filter results
            content_type_id: Content type ID to filter results
            cat1: Major category code
            cat2: Middle category code (requires cat1)
            cat3: Minor category code (requires cat1 and cat2)
            language: Override the client's default language
            page: Page number for pagination
            rows: Number of items per page
            sigunguCode: Sigungu code to filter results, areaCode is required
        Returns:
            Dictionary containing area-based tourism information with structure:
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
                    },
                    # ... more items
                ]
            }
        """
        params: Dict[str, Any] = {
            "arrange": "Q",  # Sort by {A: alphabetically, C: modified date, D: created date, O: alphabetically with image, Q: modified date with image, R: created date with image}
            "listYN": "Y",   # Return as a list
            "pageNo": str(page),
            "numOfRows": str(rows),
            "_type": "json",
        }
        
        # Add optional filters
        if area_code:
            params["areaCode"] = area_code
            if sigunguCode:
                params["sigunguCode"] = sigunguCode

        if content_type_id:
            params["contentTypeId"] = content_type_id
            
        # Add category filters if provided
        if cat1:
            params["cat1"] = cat1
            
            if cat2:
                params["cat2"] = cat2
                
                if cat3:
                    params["cat3"] = cat3
        
        # If a specific language is requested, create a new client with that language
        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.AREA_BASED_LIST_ENDPOINT, params)
            
        # Otherwise use the current client's language
        return await self._make_request(self.AREA_BASED_LIST_ENDPOINT, params)

    async def get_location_based_list(
        self,
        mapx: float,
        mapy: float,
        radius: int,
        content_type_id: Optional[str] = None,
        language: Optional[str] = None,
        page: int = 1,
        rows: int = 20,
    ) -> Dict[str, Any]:
        """
        Get a list of tourism information by location.
        
        Args:
            mapx: Map X coordinate
            mapy: Map Y coordinate
            radius: Radius in meters
            content_type_id: Content type ID from the tourism API
            language: Override the client's default language
            page: Page number for pagination
            rows: Number of items per page  
            
        Returns:
            Dictionary containing location-based tourism information with structure:
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
                        "dist": str             # Distance from the specified coordinates
                    },
                    # ... more items
                ]
            }
        """
        params: Dict[str, Any] = {
            "listYN": "Y",   # Return as a list
            "pageNo": str(page),
            "numOfRows": str(rows),
            "arrange": "Q",  # Sort by {A: alphabetically, C: modified date, D: created date, O: alphabetically with image, Q: modified date with image, R: created date with image}
            "mapX": str(mapx),  # Required by the API
            "mapY": str(mapy),  # Required by the API
            "radius": str(radius),  # Required by the API
        }

        if content_type_id:
            params["contentTypeId"] = content_type_id
        
        # If a specific language is requested, create a new client with that language
        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.LOCATION_BASED_LIST_ENDPOINT, params)
        
        # Otherwise use the current client's language
        return await self._make_request(self.LOCATION_BASED_LIST_ENDPOINT, params)

    async def search_festival(
        self,
        event_start_date: str,
        event_end_date: Optional[str] = None,
        area_code: Optional[str] = None,
        sigungu_code: Optional[str] = None,
        language: Optional[str] = None,
        page: int = 1,
        rows: int = 20
    ) -> Dict[str, Any]:
        """
        Search for festivals by date and location.
        
        Args:
            event_start_date: Start date of the event (YYYYMMDD)
            event_end_date: End date of the event (YYYYMMDD)
            area_code: Area code to filter results
            sigungu_code: Sigungu code to filter results, areaCode is required
            language: Override the client's default language
            page: Page number for pagination
            rows: Number of items per page  
            
        Returns:
            Dictionary containing festival information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
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
                    },
                    # ... more items
                ]
            }
        """
        params: Dict[str, Any] = {
            "eventStartDate": event_start_date,
            "pageNo": str(page),
            "numOfRows": str(rows),
        }

        if event_end_date:
            params["eventEndDate"] = event_end_date
        
        if area_code:
            params["areaCode"] = area_code

            if sigungu_code:
                params["sigunguCode"] = sigungu_code

        # If a specific language is requested, create a new client with that language
        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.SEARCH_FESTIVAL_ENDPOINT, params)
        
        # Otherwise use the current client's language
        return await self._make_request(self.SEARCH_FESTIVAL_ENDPOINT, params)

    async def search_stay(
        self,
        area_code: Optional[str] = None,
        sigungu_code: Optional[str] = None,
        rows: int = 20,
        page: int = 1,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for stays by area and sigungu.
        
        Args:
            area_code: Area code to filter results
            sigungu_code: Sigungu code to filter results, areaCode is required
            rows: Number of items per page
            page: Page number for pagination
            language: Override the client's default language    
            
        Returns:
            Dictionary containing accommodation information with structure:
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
                    },
                    # ... more items
                ]
            }
        """
        params: Dict[str, Any] = {
            "pageNo": str(page),
            "numOfRows": str(rows),
        }

        if area_code:
            params["areaCode"] = area_code

            if sigungu_code:
                params["sigunguCode"] = sigungu_code

        # If a specific language is requested, create a new client with that language
        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.SEARCH_STAY_ENDPOINT, params)
        
        # Otherwise use the current client's language
        return await self._make_request(self.SEARCH_STAY_ENDPOINT, params)

    async def get_detail_common(
        self,
        content_id: str,
        content_type_id: Optional[str] = None,
        language: Optional[str] = None,
        default_yn: Literal["Y", "N"] = "Y",
        first_image_yn: Literal["Y", "N"] = "Y",
        areacode_yn: Literal["Y", "N"] = "Y",
        catcode_yn: Literal["Y", "N"] = "Y",
        addrinfo_yn: Literal["Y", "N"] = "Y",
        mapinfo_yn: Literal["Y", "N"] = "Y",
        overview_yn: Literal["Y", "N"] = "Y",
        trans_guide_yn: Literal["Y", "N"] = "Y",
        rows: int = 20,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Get common information by type basic information, schematic image,
        representative image, classification information, regional information,
        address information, coordinate information, outline information, road guidance information,
        image information, linked tourism information list
        
        Args:
            content_id: Content ID from the tourism API
            content_type_id: Content type ID from the tourism API
            language: Override the client's default language
            default_yn: Whether to include default information
            first_image_yn: Whether to include first image
            areacode_yn: Whether to include area code
            catcode_yn: Whether to include category codes
            addrinfo_yn: Whether to include address info
            mapinfo_yn: Whether to include map info
            overview_yn: Whether to include overview
            trans_guide_yn: Whether to include road guidance information
            rows: Number of items per page
            page: Page number for pagination
            
        Returns:
            Dictionary containing common details about a tourism item with structure:
            {
                "total_count": int,     # Total number of matching items (typically 1)
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List containing a single item's details
                    {
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
                        "zipcode": str          # Postal code
                    }
                ]
            }
        """
            
        params: Dict[str, Any] = {
            "contentId": content_id,
            "defaultYN": default_yn,
            "firstImageYN": first_image_yn,
            "areacodeYN": areacode_yn,
            "catcodeYN": catcode_yn,
            "addrinfoYN": addrinfo_yn,
            "mapinfoYN": mapinfo_yn,
            "overviewYN": overview_yn,
            "transGuideYN": trans_guide_yn,
            "pageNo": str(page),
            "numOfRows": str(rows)
        }

        if content_type_id:
            params["contentTypeId"] = content_type_id

        # If a specific language is requested, create a new client with that language
        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.DETAIL_COMMON_ENDPOINT, params)
            
        # Otherwise use the current client's language
        return await self._make_request(self.DETAIL_COMMON_ENDPOINT, params)
    
    async def get_detail_images(
        self,
        content_id: str,
        language: Optional[str] = None,
        image_yn: Literal["Y", "N"] = "Y",
        sub_image_yn: Literal["Y", "N"] = "Y",
        rows: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Get images for a tourism item.
        
        Args:
            content_id: Content ID from the tourism API
            language: Override the client's default language
            image_yn: Y=Content image inquiry N="Restaurant" type food menu image
            sub_image_yn: Y=Inquiry of original,thumbnail image,public Nuri copyright type information N=Null
            rows: Number of items per page
            page: Page number for pagination
            
        Returns:
            Dictionary containing images for a tourism item with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of image items
                    {
                        "contentid": str,       # Content ID this image belongs to
                        "imgname": str,         # Image name
                        "originimgurl": str,    # URL of original image
                        "smallimageurl": str,   # URL of small/thumbnail image
                        "serialnum": str,       # Serial number
                        "cpyrhtDivCd": str      # Copyright division code
                    },
                    # ... more items
                ]
            }
        """
        params: Dict[str, Any] = {
            "contentId": content_id,
            "imageYN": image_yn,
            "subImageYN": sub_image_yn,
            "numOfRows": str(rows),
            "pageNo": str(page)
        }

        
        # If a specific language is requested, create a new client with that language
        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.DETAIL_IMAGE_ENDPOINT, params)
            
        # Otherwise use the current client's language
        return await self._make_request(self.DETAIL_IMAGE_ENDPOINT, params)

    async def get_detail_intro(
        self,
        content_id: str,
        content_type_id: str,
        language: Optional[str] = None,
        rows: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Function to check detailed introduction (off day, opening period, etc.)
        
        Args:
            content_id: Content ID from the tourism API
            content_type_id: Content type ID from the tourism API
            language: Override the client's default language
            rows: Number of items per page
            page: Page number for pagination
            
        Returns:
            Dictionary containing detailed introduction information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List containing a single item's intro details
                    {
                        "contentid": str,         # Content ID
                        "contenttypeid": str,     # Content type ID
                        # The following fields vary based on content_type_id:
                        
                        # Attraction specific fields may include:
                        "infocenter": str,        # Information center
                        "restdate": str,          # Rest/closing days
                        "usetime": str,           # Hours of operation
                        "parking": str,           # Parking information
                        "chkbabycarriage": str,   # Baby carriage accessibility
                        "chkpet": str,            # Pet allowance
                        "chkcreditcard": str,     # Credit card acceptance
                        
                        # Festival specific fields may include:
                        "eventstartdate": str,    # Festival start date
                        "eventenddate": str,      # Festival end date
                        "eventplace": str,        # Festival venue
                        "usetimefestival": str,   # Festival hours
                        "sponsor1": str,          # Primary sponsor
                        "sponsor2": str,          # Secondary sponsor
                        
                        # Restaurant specific fields may include:
                        "firstmenu": str,         # Main menu items
                        "treatmenu": str,         # Specialty dishes
                        "opentimefood": str,      # Opening hours
                        "restdatefood": str,      # Closing days
                        "reservationfood": str,   # Reservation information
                        
                        # Accommodation specific fields may include:
                        "checkintime": str,       # Check-in time
                        "checkouttime": str,      # Check-out time
                        "roomcount": str,         # Number of rooms
                        "reservationurl": str,    # Reservation website
                        "benikia": str,           # Benikia certification
                        "goodstay": str           # Goodstay certification
                    }
                ]
            }
            
            Note: The actual fields returned depend on the content_type_id and will vary between different types of tourism items.
        """
        params: Dict[str, Any] = {
            "contentId": content_id,
            "contentTypeId": content_type_id,
            "numOfRows": str(rows),
            "pageNo": str(page)
        }

        # If a specific language is requested, create a new client with that language
        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.DETAIL_INTRO_ENDPOINT, params)
            
        # Otherwise use the current client's language
        return await self._make_request(self.DETAIL_INTRO_ENDPOINT, params)
    
    async def get_detail_info(
        self,
        content_id: str,
        content_type_id: str,
        language: Optional[str] = None,
        rows: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Check the details of additional tourism information.
        
        Args:
            content_id: Content ID from the tourism API
            content_type_id: Content type ID from the tourism API
            language: Override the client's default language
            rows: Number of items per page
            page: Page number for pagination
            
        Returns:
            Dictionary containing additional detailed information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of additional info items
                    {
                        "contentid": str,       # Content ID this info belongs to
                        "contenttypeid": str,   # Content type ID
                        "infoname": str,        # Name of the information
                        "infotext": str,        # Detailed text information
                        "fldgubun": str,        # Field division code
                        "serialnum": str        # Serial number
                    },
                    # ... more items
                ]
            }
            
            Note: Each item in the 'items' list represents a specific piece of additional information about the tourism item.
        """
        params: Dict[str, Any] = {
            "contentId": content_id,
            "contentTypeId": content_type_id,
            "numOfRows": str(rows),
            "pageNo": str(page)
        }

        # If a specific language is requested, create a new client with that language
        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.DETAIL_INFO_ENDPOINT, params)
        
        # Otherwise use the current client's language
        return await self._make_request(self.DETAIL_INFO_ENDPOINT, params)

    async def get_area_based_sync_list(
        self,
        content_type_id: Optional[str] = None,
        area_code: Optional[str] = None,
        sigungu_code: Optional[str] = None,
        cat1: Optional[str] = None,
        cat2: Optional[str] = None,
        cat3: Optional[str] = None,
        language: Optional[str] = None,
        show_flag: Optional[Literal["0", "1"]] = None,
        rows: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Detailed function of inquiring about the tourism information synchronization list (provided whether the contents are displayed or not)
        
        Args:
            area_code: Area code from the tourism API
            content_type_id: Content type ID from the tourism API
            sigungu_code: Sigungu code from the tourism API
            cat1: Category 1 from the tourism API
            cat2: Category 2 from the tourism API
            cat3: Category 3 from the tourism API
            language: Override the client's default language
            show_flag: Show flag from the tourism API
            rows: Number of items per page
            page: Page number for pagination
            
        Returns:
            Dictionary containing synchronized tourism information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of tourism items with sync status
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
                        "showflag": str         # Display status flag
                    },
                    # ... more items
                ]
            }
        """
        params: Dict[str, Any] = {
            "numOfRows": rows,
            "pageNo": page,
            "listYN": "Y",
            "arrange": "Q",
        }
        if show_flag:
            params["showFlag"] = show_flag

        if area_code:
            params["areaCode"] = area_code

            if sigungu_code:
                params["sigunguCode"] = sigungu_code

        if cat1:
            params["cat1"] = cat1

            if cat2:
                params["cat2"] = cat2

                if cat3:
                    params["cat3"] = cat3

        if content_type_id:
            params["contentTypeId"] = content_type_id
        
        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.AREA_BASED_SYNC_LIST_ENDPOINT, params)
            
        return await self._make_request(self.AREA_BASED_SYNC_LIST_ENDPOINT, params)

    async def get_area_code_list(
        self,
        area_code: Optional[str] = None,
        language: Optional[str] = None,
        rows: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Get the list of area codes.

        Args:
            area_code: Area code from the tourism API
            language: Override the client's default language
            rows: Number of items per page
            page: Page number for pagination
            
        Returns:
            Dictionary containing area code information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of area code items
                    {
                        "code": str,            # Area code value
                        "name": str,            # Area name
                        "rnum": str             # Row number
                    },
                    # ... more items
                ]
            }
            
            If area_code is provided, returns sigungu codes for that area.
            If area_code is not provided, returns top-level area codes.
        """
        params: Dict[str, Any] = {
            "numOfRows": rows,
            "pageNo": page,
        }
        if area_code:
            params["areaCode"] = area_code

        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.AREA_CODE_LIST_ENDPOINT, params)
            
        return await self._make_request(self.AREA_CODE_LIST_ENDPOINT, params)

    async def get_category_code_list(
        self,
        content_type_id: Optional[str] = None,
        language: Optional[str] = None,
        cat1: Optional[str] = None,
        cat2: Optional[str] = None,
        cat3: Optional[str] = None,
        rows: int = 20,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Get the list of category codes.

        Args:
            content_type_id: Content type ID from the tourism API
            language: Override the client's default language
            cat1: Category 1 from the tourism API
            cat2: Category 2 from the tourism API
            cat3: Category 3 from the tourism API
            rows: Number of items per page
            page: Page number for pagination

        Returns:
            Dictionary containing category code information with structure:
            {
                "total_count": int,     # Total number of matching items
                "num_of_rows": int,     # Number of items per page
                "page_no": int,         # Current page number
                "items": [              # List of category code items
                    {
                        "code": str,            # Category code value
                        "name": str,            # Category name
                        "rnum": str             # Row number
                    },
                    # ... more items
                ]
            }
            
            The categories returned depend on the parameters provided:
            - Without any parameters: Returns top-level categories (cat1)
            - With cat1: Returns subcategories (cat2) under that cat1
            - With cat1 and cat2: Returns subcategories (cat3) under that cat2
        """
        params: Dict[str, Any] = {
            "numOfRows": rows,
            "pageNo": page,
        }

        if content_type_id:
            params["contentTypeId"] = content_type_id

        if cat1:
            params["cat1"] = cat1

            if cat2:
                params["cat2"] = cat2

                if cat3:
                    params["cat3"] = cat3
        if language and language.lower() != self.language:
            temp_client = KoreaTourismApiClient(api_key=self.api_key, language=language)
            return await temp_client._make_request(self.CATEGORY_CODE_LIST_ENDPOINT, params)
            
        return await self._make_request(self.CATEGORY_CODE_LIST_ENDPOINT, params)




if __name__ == "__main__":
    import os
    import asyncio

    api_key = os.environ.get("KOREA_TOURISM_API_KEY")
    if not api_key:
        raise ValueError("KOREA_TOURISM_API_KEY environment variable is not set")
    client = KoreaTourismApiClient(api_key=api_key)
    print(asyncio.run(client.search_by_keyword(keyword="Gyeongbokgung")))
