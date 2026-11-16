"""
Script to download all routes from RideWithGPS explore page in GPX format.
Handles pagination automatically.
"""

import requests
import json
import time
import os
from urllib.parse import urlencode, parse_qs, urlparse
from pathlib import Path


def get_routes_from_explore_api(base_url, offset=0, limit=50):
    """
    Fetch routes from RideWithGPS explore API.
    
    Args:
        base_url: The explore page URL
        offset: Pagination offset
        limit: Number of results per page
        
    Returns:
        Tuple of (routes_data, total_count, has_more)
    """
    # Parse the URL to extract query parameters
    parsed = urlparse(base_url)
    params = parse_qs(parsed.query)
    
    # Build API URL - RideWithGPS uses specific parameter format
    api_params = {
        'models': 'routes',
        'offset': offset,
    }
    
    # Copy relevant parameters from the original URL
    if 'q' in params:
        api_params['q'] = params['q'][0]
    
    # Handle elevation filter (format: "200*" means min=200)
    if 'ele' in params:
        ele_val = params['ele'][0]
        if '*' in ele_val:
            ele_min = ele_val.replace('*', '')
            api_params['elevation_min'] = ele_min
    
    # Handle length filter (format: "37*78" means min=37, max=78 in km)
    if 'length' in params:
        length_val = params['length'][0]
        if '*' in length_val:
            parts = length_val.split('*')
            if len(parts) == 2:
                api_params['length_min'] = str(int(parts[0]) * 1000)  # Convert km to meters
                api_params['length_max'] = str(int(parts[1]) * 1000)
    
    if 's' in params:
        api_params['surfaces'] = params['s'][0]
    
    api_params['sort_by'] = 'relevance desc'
    
    api_url = f"https://ridewithgps.com/explore.json?{urlencode(api_params)}"
    
    print(f"Fetching routes from API (offset={offset})...")
    print(f"API URL: {api_url}")
    
    response = requests.get(api_url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': base_url
    })
    
    if response.status_code != 200:
        print(f"Error fetching routes: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return None, 0, False
    
    try:
        data = response.json()
    except json.JSONDecodeError:
        print(f"Error parsing JSON response: {response.text[:500]}")
        return None, 0, False
    
    # Debug: print structure
    if offset == 0:
        print(f"API Response keys: {list(data.keys())}")
        if 'results' in data and len(data['results']) > 0:
            print(f"First result keys: {list(data['results'][0].keys()) if isinstance(data['results'][0], dict) else 'Not a dict'}")
    
    # Extract routes - RideWithGPS API structure may vary
    routes = []
    if 'results' in data:
        routes = data['results']
    elif 'routes' in data:
        routes = data['routes']
    elif 'data' in data:
        routes = data['data']
    
    total_count = data.get('total', data.get('count', len(routes)))
    has_more = offset + len(routes) < total_count if total_count else len(routes) > 0
    
    return routes, total_count, has_more


def download_route_gpx(route_id, output_dir, route_name=None, privacy_code=None):
    """
    Download GPX file for a specific route.
    
    Args:
        route_id: The route ID
        output_dir: Directory to save the GPX file
        route_name: Optional route name for filename
        privacy_code: Optional privacy code for private routes
        
    Returns:
        True if successful, False otherwise
    """
    # Try different GPX download URLs
    gpx_urls = []
    
    # Base URL
    base_url = f"https://ridewithgps.com/routes/{route_id}"
    
    # Add privacy code if provided
    privacy_param = f"?privacy_code={privacy_code}" if privacy_code else ""
    
    gpx_urls = [
        f"{base_url}.gpx{privacy_param}",
        f"{base_url}/route.gpx{privacy_param}",
        f"{base_url}/export.gpx{privacy_param}",
        f"{base_url}/download.gpx{privacy_param}",
        f"{base_url}/gpx{privacy_param}",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/gpx+xml, application/xml, text/xml, */*',
        'Referer': f'https://ridewithgps.com/routes/{route_id}'
    }
    
    for gpx_url in gpx_urls:
        try:
            response = requests.get(gpx_url, headers=headers, timeout=15, allow_redirects=True)
            
            # Debug first attempt
            if gpx_url == gpx_urls[0]:
                print(f"    Trying: {gpx_url[:80]}... Status: {response.status_code}")
            
            # Check if response is valid GPX
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                content = response.text if hasattr(response, 'text') else response.content.decode('utf-8', errors='ignore')
                
                # Check if it's GPX by content type or by checking the content
                is_gpx = (
                    'gpx' in content_type or 
                    'xml' in content_type or
                    (content.strip().startswith('<?xml') and '<gpx' in content.lower()) or
                    content.strip().startswith('<gpx')
                )
                
                if is_gpx and len(content) > 100:  # Make sure it's not just an error message
                    # Generate filename
                    if route_name:
                        # Sanitize route name for filename
                        safe_name = "".join(c for c in route_name if c.isalnum() or c in (' ', '-', '_')).strip()
                        safe_name = safe_name.replace(' ', '_')[:50]  # Limit length
                        filename = f"{safe_name}_{route_id}.gpx"
                    else:
                        filename = f"route_{route_id}.gpx"
                    
                    output_path = Path(output_dir) / filename
                    
                    # Write file
                    with open(output_path, 'wb') as f:
                        if isinstance(content, str):
                            f.write(content.encode('utf-8'))
                        else:
                            f.write(response.content)
                    
                    print(f"  [OK] Downloaded route {route_id} -> {filename}")
                    return True
                elif response.status_code == 200:
                    # Got 200 but not GPX - might be HTML error page
                    if len(content) < 500:
                        print(f"    Response (not GPX): {content[:200]}")
        except Exception as e:
            # Try next URL
            if gpx_url == gpx_urls[0]:
                print(f"    Exception: {str(e)[:100]}")
            continue
    
    # If all URLs failed, try getting route JSON to see if there's a download link
    try:
        json_url = f"https://ridewithgps.com/routes/{route_id}.json"
        if privacy_code:
            json_url += f"?privacy_code={privacy_code}"
        
        json_response = requests.get(json_url, headers=headers, timeout=10)
        if json_response.status_code == 200:
            route_data = json_response.json()
            # Check if there's a GPX URL in the response
            if 'gpx_url' in route_data or 'download_url' in route_data:
                gpx_url = route_data.get('gpx_url') or route_data.get('download_url')
                if gpx_url:
                    response = requests.get(gpx_url, headers=headers, timeout=15)
                    if response.status_code == 200:
                        content = response.text if hasattr(response, 'text') else response.content.decode('utf-8', errors='ignore')
                        if '<gpx' in content.lower():
                            filename = f"route_{route_id}.gpx" if not route_name else f"{route_name.replace(' ', '_')[:50]}_{route_id}.gpx"
                            output_path = Path(output_dir) / filename
                            with open(output_path, 'wb') as f:
                                f.write(content.encode('utf-8') if isinstance(content, str) else response.content)
                            print(f"  [OK] Downloaded route {route_id} via JSON -> {filename}")
                            return True
    except:
        pass
    
    print(f"  [FAILED] Failed to download route {route_id}")
    return False


def download_all_routes(base_url, output_dir="docs/gpx routes/ridewithgps"):
    """
    Download all routes from a RideWithGPS explore page.
    
    Args:
        base_url: The explore page URL
        output_dir: Directory to save GPX files
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Starting download of routes from RideWithGPS...")
    print(f"Output directory: {output_path.absolute()}")
    print()
    
    offset = 0
    limit = 50
    total_downloaded = 0
    total_failed = 0
    all_route_ids = set()
    
    while True:
        # Fetch routes from API
        routes, total_count, has_more = get_routes_from_explore_api(base_url, offset, limit)
        
        if not routes:
            print("No more routes found or error occurred.")
            break
        
        print(f"Found {len(routes)} routes (Total: {total_count}, Offset: {offset})")
        
        # Extract route IDs, names, and privacy codes
        route_data = []
        for i, route in enumerate(routes):
            route_id = None
            route_name = None
            privacy_code = None
            
            if isinstance(route, dict):
                # Try different possible keys for route ID
                route_id = route.get('id')
                if route_id is None:
                    route_id = route.get('route_id')
                if route_id is None:
                    route_id = route.get('routeId')
                if route_id is None and isinstance(route.get('route'), dict):
                    route_id = route.get('route', {}).get('id')
                
                # Try to get route name
                route_name = route.get('name')
                if route_name is None:
                    route_name = route.get('route_name')
                if route_name is None and isinstance(route.get('route'), dict):
                    route_name = route.get('route', {}).get('name')
                
                # Get privacy code if available
                privacy_code = route.get('privacy_code')
                
                # Debug first route
                if i == 0:
                    print(f"  [DEBUG] First route - id={route_id}, name={route_name}, privacy_code={privacy_code}")
                
                if route_id is not None:  # Check for None explicitly, not truthiness (0 is valid ID)
                    route_data.append((str(route_id), route_name, privacy_code))
                else:
                    print(f"  [WARNING] Could not extract ID from route {i}: id value = {route.get('id')}")
            elif isinstance(route, str):
                # If it's a string like "Route-123456", extract the ID
                if route.startswith('Route-'):
                    route_id = route.replace('Route-', '')
                    route_data.append((route_id, None))
        
        print(f"Extracted {len(route_data)} route IDs from {len(routes)} results")
        
        # Download each route
        for route_id, route_name, privacy_code in route_data:
            if route_id in all_route_ids:
                print(f"  [SKIP] Skipping duplicate route {route_id}")
                continue
            
            all_route_ids.add(route_id)
            
            if download_route_gpx(route_id, output_path, route_name, privacy_code):
                total_downloaded += 1
            else:
                total_failed += 1
            
            # Be polite - small delay between downloads
            time.sleep(0.5)
        
        # Check if there are more pages
        if not has_more:
            break
        
        offset += limit
        print()
        time.sleep(1)  # Small delay between pages
    
    print()
    print(f"Download complete!")
    print(f"  Total routes found: {len(all_route_ids)}")
    print(f"  Successfully downloaded: {total_downloaded}")
    print(f"  Failed: {total_failed}")


if __name__ == "__main__":
    # The URL from the user
    explore_url = "https://ridewithgps.com/explore?S=rg7mnz&b=u&ele=200*&length=37*78&m=routes&p=10!30!Rtw7psRq68g5Rvdgs4Rrj976Rv68qkRtdn41Rl7t2uRqzfeoRu54kxRgd762Rtuxs5Rkh4tgRo0zvrRo0hvlRi43sxRi6x9qRtjp7cReo98sRde1jrRqdouv*10!40!Rtuxs5Rkh4tgRo0zvrRo0hvlRi43sxRi6x9qRu9t5rRrry31Rn0kjaRh42y0Rv7gvjR43y3mRtqoyvRvqg86Rtjp7cReo98sRde1jrRqdouvRlpd7uRsn3j1*10!50!Rv7gvjR43y3mRtqoyvRvqg86Rlj0xvR17wdlRg7mnzRngwxlRecov3Rvb8i0Rq5o4iRgjve8Rtjp7cReo98sRde1jrRqdouvRlpd7uRsn3j1RnrqvpR3x7aq&q=Aarhus%20C&s=paved"
    
    download_all_routes(explore_url)

