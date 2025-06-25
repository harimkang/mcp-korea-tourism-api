import pytest
import respx
import httpx
from urllib.parse import urlencode, quote
from mcp_tourism.api_client import KoreaTourismApiClient, LANGUAGE_SERVICE_MAP

# Sample successful response structure from the API
MOCK_SUCCESS_RESPONSE = {
    "response": {
        "header": {"resultCode": "0000", "resultMsg": "OK"},
        "body": {
            "items": {
                "item": [
                    {
                        "addr1": "161 Sajik-ro, Jongno-gu, Seoul",
                        "addr2": "",
                        "areacode": "1",
                        "cat1": "A02",
                        "cat2": "A0201",
                        "cat3": "A02010100",
                        "contentid": "264337",
                        "contenttypeid": "76",
                        "createdtime": "20110226022850",
                        "firstimage": "http://tong.visitkorea.or.kr/cms/resource/33/2678633_image2_1.jpg",
                        "firstimage2": "http://tong.visitkorea.or.kr/cms/resource/33/2678633_image3_1.jpg",
                        "cpyrhtDivCd": "Type3",
                        "mapx": "126.9769930325",
                        "mapy": "37.5788222356",
                        "mlevel": "6",
                        "modifiedtime": "20241010094040",
                        "sigungucode": "23",
                        "tel": "+82-2-3700-3900",
                        "title": "Gyeongbokgung Palace (경복궁)",
                    }
                ]
            },
            "numOfRows": 1,
            "pageNo": 1,
            "totalCount": 1,
        },
    }
}

# Sample error response structure
MOCK_ERROR_RESPONSE = {
    "response": {
        "header": {"resultCode": "99", "resultMsg": "SERVICE ERROR"},
        "body": {},
    }
}


@pytest.mark.asyncio
@respx.mock
async def test_search_by_keyword_success(client: KoreaTourismApiClient):
    """Tests successful search_by_keyword call."""
    keyword = "Gyeongbokgung"
    area_code = "1"
    language = "en"
    api_key_encoded = quote(
        client.api_key, safe=""
    )  # API key should be URL encoded in the request

    # Construct expected params and URL
    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "keyword": keyword,
        "arrange": "Q",
        "listYN": "Y",
        "areaCode": area_code,
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.SEARCH_KEYWORD_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    # Mock the specific request
    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    # Call the method
    results = await client.search_by_keyword(
        keyword=keyword, area_code=area_code, language=language
    )

    # Assertions
    assert results["total_count"] == 1
    assert len(results["items"]) == 1
    assert results["items"][0]["title"] == "Gyeongbokgung Palace (경복궁)"
    assert results["items"][0]["contentid"] == "264337"


@pytest.mark.asyncio
@respx.mock
async def test_search_by_keyword_different_language(client: KoreaTourismApiClient):
    """Tests search_by_keyword with a language different from the client's default."""
    keyword = "경복궁"
    language = "ko"  # Assuming 'ko' is supported and mapped in LANGUAGE_SERVICE_MAP
    # Need to add 'ko': 'KorService1' to LANGUAGE_SERVICE_MAP for this test
    LANGUAGE_SERVICE_MAP["ko"] = "KorService1"  # Temporarily add for test

    api_key_encoded = quote(client.api_key, safe="")

    # Construct expected params and URL for the Korean service
    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "keyword": keyword,
        "arrange": "Q",
        "listYN": "Y",
    }
    encoded_params = urlencode(expected_params)
    # Note the use of LANGUAGE_SERVICE_MAP['ko']
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.SEARCH_KEYWORD_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    # Mock the request to the Korean service endpoint
    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )  # Use same mock response for simplicity

    # Call the method with the specific language
    results = await client.search_by_keyword(keyword=keyword, language=language)

    # Assertions (check if the structure is correct, content might differ for 'ko')
    assert "total_count" in results
    assert "items" in results
    del LANGUAGE_SERVICE_MAP["ko"]  # Clean up temp addition


@pytest.mark.asyncio
@respx.mock
async def test_search_by_keyword_caching(client: KoreaTourismApiClient):
    """Tests if responses are cached."""
    keyword = "Namsan"
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "keyword": keyword,
        "arrange": "Q",
        "listYN": "Y",
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.SEARCH_KEYWORD_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    # Mock the request
    route = respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    # First call - should hit the API
    await client.search_by_keyword(keyword=keyword, language=language)
    assert route.called is True
    assert route.call_count == 1

    # Second call - should hit the cache
    await client.search_by_keyword(keyword=keyword, language=language)
    assert route.call_count == 1  # Call count should not increase


@pytest.mark.asyncio
@respx.mock
async def test_api_error_handling(client: KoreaTourismApiClient):
    """Tests error handling for non-200 responses."""
    keyword = "ErrorTest"
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "keyword": keyword,
        "arrange": "Q",
        "listYN": "Y",
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.SEARCH_KEYWORD_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    # Mock a 500 server error response
    respx.get(expected_url).mock(
        return_value=httpx.Response(500, json=MOCK_ERROR_RESPONSE)
    )

    # Check if the correct exception is raised (requires importing the exception)
    from mcp_tourism.api_client import TourismApiServerError

    with pytest.raises(TourismApiServerError):
        await client.search_by_keyword(keyword=keyword, language=language)


@pytest.mark.asyncio
@respx.mock
async def test_get_area_based_list_success(client: KoreaTourismApiClient):
    """Tests successful get_area_based_list call."""
    area_code = "1"
    content_type_id = "76"
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "arrange": "Q",
        "listYN": "Y",
        "areaCode": area_code,
        "contentTypeId": content_type_id,
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.AREA_BASED_LIST_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.get_area_based_list(
        area_code=area_code, content_type_id=content_type_id, language=language
    )

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_get_location_based_list_success(client: KoreaTourismApiClient):
    """Tests successful get_location_based_list call."""
    mapx = 126.9780
    mapy = 37.5665
    radius = 1000
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "arrange": "Q",
        "listYN": "Y",
        "mapX": str(mapx),
        "mapY": str(mapy),
        "radius": str(radius),
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.LOCATION_BASED_LIST_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.get_location_based_list(
        mapx=mapx, mapy=mapy, radius=radius, language=language
    )

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_search_festival_success(client: KoreaTourismApiClient):
    """Tests successful search_festival call."""
    start_date = "20250501"
    end_date = "20250531"
    area_code = "1"
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "eventStartDate": start_date,
        "eventEndDate": end_date,
        "areaCode": area_code,
        "arrange": "Q",
        "listYN": "Y",
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.SEARCH_FESTIVAL_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.search_festival(
        event_start_date=start_date,
        event_end_date=end_date,
        area_code=area_code,
        language=language,
    )

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_search_stay_success(client: KoreaTourismApiClient):
    """Tests successful search_stay call."""
    area_code = "1"
    sigungu_code = "23"
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "areaCode": area_code,
        "sigunguCode": sigungu_code,
        "arrange": "Q",
        "listYN": "Y",
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.SEARCH_STAY_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.search_stay(
        area_code=area_code, sigungu_code=sigungu_code, language=language
    )

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_get_detail_common_success(client: KoreaTourismApiClient):
    """Tests successful get_detail_common call."""
    content_id = "264337"
    content_type_id = "76"
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "contentId": content_id,
        "contentTypeId": content_type_id,
        "defaultYN": "Y",
        "firstImageYN": "Y",
        "areacodeYN": "Y",
        "catcodeYN": "Y",
        "addrinfoYN": "Y",
        "mapinfoYN": "Y",
        "overviewYN": "Y",
        "transGuideYN": "Y",
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.DETAIL_COMMON_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.get_detail_common(
        content_id=content_id, content_type_id=content_type_id, language=language
    )

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_get_detail_images_success(client: KoreaTourismApiClient):
    """Tests successful get_detail_images call."""
    content_id = "264337"
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "contentId": content_id,
        "imageYN": "Y",
        "subImageYN": "Y",
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.DETAIL_IMAGE_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.get_detail_images(content_id=content_id, language=language)

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_get_detail_intro_success(client: KoreaTourismApiClient):
    """Tests successful get_detail_intro call."""
    content_id = "264337"
    content_type_id = "76"
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "contentId": content_id,
        "contentTypeId": content_type_id,
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.DETAIL_INTRO_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.get_detail_intro(
        content_id=content_id, content_type_id=content_type_id, language=language
    )

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_get_detail_info_success(client: KoreaTourismApiClient):
    """Tests successful get_detail_info call."""
    content_id = "264337"
    content_type_id = "76"
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "contentId": content_id,
        "contentTypeId": content_type_id,
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.DETAIL_INFO_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.get_detail_info(
        content_id=content_id, content_type_id=content_type_id, language=language
    )

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_get_area_code_list_top_level(client: KoreaTourismApiClient):
    """Tests successful get_area_code_list for top-level areas."""
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.AREA_CODE_LIST_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.get_area_code_list(language=language)

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_get_area_code_list_sub_level(client: KoreaTourismApiClient):
    """Tests successful get_area_code_list for sub-level areas (sigungu)."""
    area_code = "1"  # Seoul
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "areaCode": area_code,
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.AREA_CODE_LIST_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.get_area_code_list(area_code=area_code, language=language)

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_get_category_code_list_success(client: KoreaTourismApiClient):
    """Tests successful get_category_code_list call."""
    content_type_id = "76"
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "contentTypeId": content_type_id,
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.CATEGORY_CODE_LIST_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.get_category_code_list(
        content_type_id=content_type_id, language=language
    )

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_search_by_keyword_with_sigungu(client: KoreaTourismApiClient):
    """Tests search_by_keyword with area_code and sigungu_code."""
    keyword = "Restaurant"
    area_code = "1"  # Seoul
    sigungu_code = "23"  # Jongno-gu
    language = "en"
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "keyword": keyword,
        "arrange": "Q",
        "listYN": "Y",
        "areaCode": area_code,
        "sigunguCode": sigungu_code,
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.SEARCH_KEYWORD_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.search_by_keyword(
        keyword=keyword,
        area_code=area_code,
        sigungu_code=sigungu_code,
        language=language,
    )

    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_get_area_based_list_pagination(client: KoreaTourismApiClient):
    """Tests get_area_based_list with pagination parameters."""
    area_code = "1"
    language = "en"
    page = 2
    rows = 5
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": str(rows),
        "pageNo": str(page),
        "_type": "json",
        "arrange": "Q",
        "listYN": "Y",
        "areaCode": area_code,
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.AREA_BASED_LIST_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    # Modify mock response slightly to reflect pagination if needed, or use generic one
    mock_paginated_response = MOCK_SUCCESS_RESPONSE.copy()
    # Deep copy nested dictionaries to avoid modifying the original MOCK_SUCCESS_RESPONSE
    mock_paginated_response["response"] = MOCK_SUCCESS_RESPONSE["response"].copy()
    mock_paginated_response["response"]["body"] = MOCK_SUCCESS_RESPONSE["response"][
        "body"
    ].copy()

    mock_paginated_response["response"]["body"]["pageNo"] = page
    mock_paginated_response["response"]["body"]["numOfRows"] = rows

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=mock_paginated_response)
    )

    results = await client.get_area_based_list(
        area_code=area_code, language=language, page=page, rows=rows
    )

    assert results["page_no"] == page
    assert results["num_of_rows"] == rows
    assert "total_count" in results
    assert "items" in results


@pytest.mark.asyncio
@respx.mock
async def test_get_category_code_list_sub_category(client: KoreaTourismApiClient):
    """Tests get_category_code_list for sub-categories (cat2)."""
    language = "en"
    cat1 = "A01"  # Example: Nature category
    api_key_encoded = quote(client.api_key, safe="")

    expected_params = {
        "MobileOS": "ETC",
        "MobileApp": "MobileApp",
        "numOfRows": "20",
        "pageNo": "1",
        "_type": "json",
        "cat1": cat1,
    }
    encoded_params = urlencode(expected_params)
    expected_url = f"{client.BASE_URL}/{LANGUAGE_SERVICE_MAP[language]}{client.CATEGORY_CODE_LIST_ENDPOINT}?serviceKey={api_key_encoded}&{encoded_params}"

    respx.get(expected_url).mock(
        return_value=httpx.Response(200, json=MOCK_SUCCESS_RESPONSE)
    )

    results = await client.get_category_code_list(cat1=cat1, language=language)

    assert "total_count" in results
    assert "items" in results


# TODO: Add more tests for specific parameter combinations if needed.
# TODO: Consider adding tests for rate limiting and retry behavior, although they can be complex to mock accurately.
