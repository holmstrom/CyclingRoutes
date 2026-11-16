"""
Script to download all routes from RideWithGPS explore page using browser automation.
This script navigates through all pages and downloads GPX files for each route.
"""

import requests
import json
import time
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode
import sys

# Add src to path to import GPX generator
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.gpx.generator import create_gpx_from_coordinates, save_gpx


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
    
    # Handle polygon filter (p parameter) - this is important for getting all results
    if 'p' in params:
        api_params['p'] = params['p'][0]
    
    # Handle other parameters that might be needed
    if 'S' in params:
        api_params['S'] = params['S'][0]
    if 'b' in params:
        api_params['b'] = params['b'][0]
    if 'm' in params:
        api_params['m'] = params['m'][0]
    
    api_params['sort_by'] = 'relevance desc'
    
    api_url = f"https://ridewithgps.com/explore.json?{urlencode(api_params)}"
    
    print(f"Fetching routes from API (offset={offset})...")
    
    # Use session to maintain cookies
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': base_url
    })
    
    response = session.get(api_url, timeout=15)
    
    if response.status_code != 200:
        print(f"Error fetching routes: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        # Return empty list instead of None to allow pagination to continue
        return [], 0, False, session
    
    try:
        data = response.json()
    except json.JSONDecodeError:
        print(f"Error parsing JSON response: {response.text[:500]}")
        return None, 0, False, session
    
    # Extract routes - RideWithGPS API structure may vary
    routes = []
    if 'results' in data:
        routes = data['results']
    elif 'routes' in data:
        routes = data['routes']
    elif 'data' in data:
        routes = data['data']
    
    total_count = data.get('total_count', data.get('total', data.get('count', len(routes))))
    # Continue paginating if we got routes, even if total_count suggests otherwise
    # (the API might not return accurate total_count with polygon filters)
    has_more = len(routes) > 0
    
    return routes, total_count, has_more, session


def download_route_gpx_with_session(route_id, session, output_dir, route_name=None, privacy_code=None):
    """
    Download GPX file for a specific route using a session with cookies.
    
    Args:
        route_id: The route ID
        session: requests.Session object with cookies
        output_dir: Directory to save the GPX file
        route_name: Optional route name for filename
        privacy_code: Optional privacy code for private routes
        
    Returns:
        True if successful, False otherwise
    """
    # Try different GPX download URLs
    base_url = f"https://ridewithgps.com/routes/{route_id}"
    privacy_param = f"?privacy_code={privacy_code}" if privacy_code else ""
    
    gpx_urls = [
        f"{base_url}.gpx{privacy_param}",
        f"{base_url}/route.gpx{privacy_param}",
        f"{base_url}/export.gpx{privacy_param}",
        f"{base_url}/download.gpx{privacy_param}",
        f"{base_url}/gpx{privacy_param}",
    ]
    
    # Update headers for GPX download
    session.headers.update({
        'Accept': 'application/gpx+xml, application/xml, text/xml, */*',
        'Referer': base_url
    })
    
    for gpx_url in gpx_urls:
        try:
            response = session.get(gpx_url, timeout=15, allow_redirects=True)
            
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
                
                if is_gpx and len(content) > 100:
                    # Generate filename
                    if route_name:
                        safe_name = "".join(c for c in route_name if c.isalnum() or c in (' ', '-', '_')).strip()
                        safe_name = safe_name.replace(' ', '_')[:50]
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
                    
        except Exception as e:
            continue
    
    # Try getting route JSON to extract GPX data or URL
    try:
        json_url = f"https://ridewithgps.com/routes/{route_id}.json"
        if privacy_code:
            json_url += f"?privacy_code={privacy_code}"
        
        session.headers.update({'Accept': 'application/json'})
        json_response = session.get(json_url, timeout=10)
        
        if json_response.status_code == 200:
            route_data = json_response.json()
            
            # Check if there's a GPX URL in the response
            if 'gpx_url' in route_data or 'download_url' in route_data:
                gpx_url = route_data.get('gpx_url') or route_data.get('download_url')
                if gpx_url:
                    session.headers.update({'Accept': 'application/gpx+xml, application/xml, text/xml, */*'})
                    response = session.get(gpx_url, timeout=15)
                    if response.status_code == 200:
                        content = response.text if hasattr(response, 'text') else response.content.decode('utf-8', errors='ignore')
                        if '<gpx' in content.lower():
                            filename = f"route_{route_id}.gpx" if not route_name else f"{route_name.replace(' ', '_')[:50]}_{route_id}.gpx"
                            output_path = Path(output_dir) / filename
                            with open(output_path, 'wb') as f:
                                f.write(content.encode('utf-8') if isinstance(content, str) else response.content)
                            print(f"  [OK] Downloaded route {route_id} via JSON -> {filename}")
                            return True
            
            # Try to construct GPX from track points in JSON
            track_points = None
            if 'track_points' in route_data:
                track_points = route_data['track_points']
            elif 'points' in route_data:
                track_points = route_data['points']
            elif 'track' in route_data and isinstance(route_data['track'], dict):
                if 'track_points' in route_data['track']:
                    track_points = route_data['track']['track_points']
                elif 'points' in route_data['track']:
                    track_points = route_data['track']['points']
            
            if track_points and len(track_points) > 0:
                # Extract coordinates from track points
                coordinates = []
                for point in track_points:
                    if isinstance(point, dict):
                        # Try different possible formats
                        if 'lat' in point and 'lng' in point:
                            coordinates.append((float(point['lat']), float(point['lng'])))
                        elif 'latitude' in point and 'longitude' in point:
                            coordinates.append((float(point['latitude']), float(point['longitude'])))
                        elif 'y' in point and 'x' in point:  # Sometimes lat/lon are called y/x
                            coordinates.append((float(point['y']), float(point['x'])))
                        elif len(point) >= 2:  # Try as list [lat, lon] or [lon, lat]
                            try:
                                # Try [lat, lon] first
                                lat, lon = float(point[0]), float(point[1])
                                # Validate reasonable lat/lon values
                                if -90 <= lat <= 90 and -180 <= lon <= 180:
                                    coordinates.append((lat, lon))
                            except (ValueError, IndexError, TypeError):
                                pass
                
                if len(coordinates) > 0:
                    # Create GPX from coordinates
                    route_name_for_gpx = route_name or f"Route {route_id}"
                    description = route_data.get('description', '') or ''
                    if 'distance' in route_data:
                        description += f"\nDistance: {route_data.get('distance', 0):.2f} km"
                    if 'elevation_gain' in route_data:
                        description += f"\nElevation gain: {route_data.get('elevation_gain', 0):.0f} m"
                    
                    gpx = create_gpx_from_coordinates(
                        coordinates,
                        name=route_name_for_gpx,
                        description=description.strip()
                    )
                    
                    # Generate filename
                    if route_name:
                        safe_name = "".join(c for c in route_name if c.isalnum() or c in (' ', '-', '_')).strip()
                        safe_name = safe_name.replace(' ', '_')[:50]
                        filename = f"{safe_name}_{route_id}.gpx"
                    else:
                        filename = f"route_{route_id}.gpx"
                    
                    output_path = Path(output_dir) / filename
                    
                    # Save GPX file
                    if save_gpx(gpx, str(output_path)):
                        print(f"  [OK] Created GPX from JSON for route {route_id} -> {filename} ({len(coordinates)} points)")
                        return True
                    else:
                        print(f"  [FAILED] Could not save GPX file for route {route_id}")
    except Exception as e:
        print(f"  [ERROR] Exception processing route {route_id}: {str(e)[:100]}")
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
    session = None
    
    while True:
        # Fetch routes from API
        routes, total_count, has_more, session = get_routes_from_explore_api(base_url, offset, limit)
        
        if not routes or len(routes) == 0:
            print(f"No more routes found at offset {offset}.")
            # Try smaller increments to catch any routes in gaps
            if offset % 50 == 0 and offset < 500:
                # Try offsets +10, +20, +30, +40 to catch any routes in the gap
                found_more = False
                for small_offset in [offset + 10, offset + 20, offset + 30, offset + 40]:
                    print(f"Checking offset {small_offset}...")
                    test_routes, _, _, _ = get_routes_from_explore_api(base_url, small_offset, limit)
                    if test_routes and len(test_routes) > 0:
                        print(f"Found {len(test_routes)} routes at offset {small_offset}, continuing...")
                        offset = small_offset
                        found_more = True
                        break
                    time.sleep(0.5)  # Small delay between checks
                if not found_more:
                    break
                continue
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
                
                if route_id is not None:
                    route_data.append((str(route_id), route_name, privacy_code))
        
        print(f"Extracted {len(route_data)} route IDs from {len(routes)} results")
        
        # Download each route
        for route_id, route_name, privacy_code in route_data:
            if route_id in all_route_ids:
                print(f"  [SKIP] Skipping duplicate route {route_id}")
                continue
            
            all_route_ids.add(route_id)
            
            if download_route_gpx_with_session(route_id, session, output_path, route_name, privacy_code):
                total_downloaded += 1
            else:
                total_failed += 1
            
            # Be polite - small delay between downloads
            time.sleep(0.5)
        
        # Check if there are more pages
        # Continue if we got routes, or if we haven't reached a reasonable limit
        if len(routes) == 0:
            print("No more routes found.")
            break
        
        # Safety limit - don't paginate forever
        if offset >= 1000:  # Max 1000 routes (20 pages of 50)
            print(f"Reached safety limit of {offset} routes. Stopping.")
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

