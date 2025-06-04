import argparse
import json
from datetime import datetime, date, time, timedelta
import os
from typing import List, Dict, Any, Optional, Tuple, Union # Added Union

import googlemaps
import pandas as pd
from haversine import haversine, Unit
from dateutil import parser as date_parser

# --- Configuration & Constants ---
E7_DIVISOR = 10000000.0
DEFAULT_PROXIMITY_RADIUS_METERS = 500
MIN_PATH_POINTS_FOR_DISTANCE_CALC = 2 # Min points in timelinePath to calculate distance

# --- Helper Functions ---
def e7_to_decimal(e7_val: int) -> float:
    """Converts an E7 coordinate value to decimal degrees."""
    return e7_val / E7_DIVISOR

def parse_degree_lat_lon_string(lat_lon_str: Optional[str]) -> Optional[Tuple[float, float]]:
    """Parses a string like '43.8946875°, -79.5587437°' into (lat, lon) tuple."""
    if not lat_lon_str:
        return None
    try:
        parts = lat_lon_str.replace('°', '').split(',')
        if len(parts) == 2:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            return lat, lon
    except ValueError as e:
        print(f"Warning: Could not parse degree lat/lon string: {lat_lon_str} - {e}")
    return None

def get_datetime_from_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """Parses a timestamp string into a datetime object."""
    if not ts_str:
        return None
    try:
        # Handle 'Z' for UTC explicitly if dateutil doesn't automatically
        dt_obj = date_parser.isoparse(ts_str)
        return dt_obj
    except ValueError:
        print(f"Warning: Could not parse timestamp: {ts_str}")
        return None

def is_near(
    coord1: Optional[Tuple[float, float]],
    coord2: Optional[Tuple[float, float]],
    radius_meters: float
) -> bool:
    """Checks if coord1 is within radius_meters of coord2."""
    if not coord1 or not coord2:
        return False
    try:
        distance_m = haversine(coord1, coord2, unit=Unit.METERS)
        return distance_m <= radius_meters
    except Exception as e:
        print(f"Warning: Could not calculate distance for proximity check {coord1} vs {coord2}: {e}")
        return False


def geocode_address(
    gmaps_client: googlemaps.Client,
    address_str: str
) -> List[Dict[str, Any]]:
    """Geocodes an address string and returns a list of potential matches."""
    try:
        geocode_result = gmaps_client.geocode(address_str)
        return geocode_result
    except Exception as e:
        print(f"Error geocoding address '{address_str}': {e}")
        return []

def select_geocoded_location(
    options: List[Dict[str, Any]],
    location_type_name: str
) -> Optional[Dict[str, Any]]:
    """
    Prints geocoding options and selects the first one.
    Returns the selected location object or None if no suitable option.
    """
    print(f"\n--- Geocoding results for {location_type_name} ---")
    if not options:
        print("No geocoding results found.")
        return None

    for i, result in enumerate(options):
        formatted_address = result.get('formatted_address', 'N/A')
        lat = result.get('geometry', {}).get('location', {}).get('lat', 'N/A')
        lng = result.get('geometry', {}).get('location', {}).get('lng', 'N/A')
        print(f"Match {i+1}: {formatted_address} (Lat: {lat}, Lng: {lng})")

    selected_option = options[0] # Auto-select the first result
    print(f"Selected for {location_type_name}: {selected_option.get('formatted_address')}")
    print("--------------------------------------")
    return selected_option

# --- Timeline Parsing Logic ---

def calculate_distance_from_timeline_path(timeline_path_list: List[Dict[str, str]]) -> float:
    """Calculates distance in km from a list of timelinePath points."""
    total_distance_km = 0.0
    if len(timeline_path_list) < MIN_PATH_POINTS_FOR_DISTANCE_CALC:
        return 0.0

    for i in range(len(timeline_path_list) - 1):
        point_a_str = timeline_path_list[i].get('point')
        point_b_str = timeline_path_list[i+1].get('point')

        coord_a = parse_degree_lat_lon_string(point_a_str)
        coord_b = parse_degree_lat_lon_string(point_b_str)

        if coord_a and coord_b:
            total_distance_km += haversine(coord_a, coord_b, unit=Unit.KILOMETERS)
    return total_distance_km

def parse_timeline_objects(
    timeline_objects_list: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses data from 'timelineObjects' structure."""
    parsed_visits = []
    parsed_travels = []

    for obj in timeline_objects_list:
        if 'placeVisit' in obj:
            visit = obj['placeVisit']
            location = visit.get('location', {})
            duration = visit.get('duration', {})
            
            lat = location.get('latitudeE7')
            lon = location.get('longitudeE7')
            start_ts_str = duration.get('startTimestamp')
            end_ts_str = duration.get('endTimestamp')

            if lat is not None and lon is not None and start_ts_str and end_ts_str:
                parsed_visits.append({
                    "type": "visit",
                    "lat": e7_to_decimal(lat),
                    "lon": e7_to_decimal(lon),
                    "startTimestamp": get_datetime_from_timestamp(start_ts_str),
                    "endTimestamp": get_datetime_from_timestamp(end_ts_str),
                    "placeId": location.get('placeId'),
                    "address": location.get('address') or location.get('name'),
                    "source_format": "timelineObjects"
                })
        elif 'activitySegment' in obj:
            segment = obj['activitySegment']
            duration = segment.get('duration', {})
            start_ts_str = duration.get('startTimestamp')
            end_ts_str = duration.get('endTimestamp')
            distance_meters = segment.get('distance')

            if start_ts_str and end_ts_str and isinstance(distance_meters, (int, float)):
                start_loc = segment.get('startLocation', {})
                end_loc = segment.get('endLocation', {})
                parsed_travels.append({
                    "type": "travel",
                    "startTimestamp": get_datetime_from_timestamp(start_ts_str),
                    "endTimestamp": get_datetime_from_timestamp(end_ts_str),
                    "distance_km": distance_meters / 1000.0,
                    "activityType": segment.get('activityType'),
                    "startLat": e7_to_decimal(start_loc['latitudeE7']) if 'latitudeE7' in start_loc else None,
                    "startLon": e7_to_decimal(start_loc['longitudeE7']) if 'longitudeE7' in start_loc else None,
                    "endLat": e7_to_decimal(end_loc['latitudeE7']) if 'latitudeE7' in end_loc else None,
                    "endLon": e7_to_decimal(end_loc['longitudeE7']) if 'longitudeE7' in end_loc else None,
                    "source_format": "timelineObjects"
                })
    return parsed_visits, parsed_travels


def parse_semantic_segments(
    semantic_segments_list: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses data from 'semanticSegments' structure."""
    parsed_visits = []
    parsed_travels = []

    for segment in semantic_segments_list:
        start_ts_str = segment.get('startTime')
        end_ts_str = segment.get('endTime')
        start_ts = get_datetime_from_timestamp(start_ts_str)
        end_ts = get_datetime_from_timestamp(end_ts_str)

        if not start_ts or not end_ts:
            continue

        if 'visit' in segment:
            visit_data = segment['visit']
            top_candidate = visit_data.get('topCandidate', {})
            place_location = top_candidate.get('placeLocation', {})
            lat_lon_str = place_location.get('latLng')
            coords = parse_degree_lat_lon_string(lat_lon_str)

            if coords:
                parsed_visits.append({
                    "type": "visit",
                    "lat": coords[0],
                    "lon": coords[1],
                    "startTimestamp": start_ts,
                    "endTimestamp": end_ts,
                    "placeId": top_candidate.get('placeId'),
                    # Address might not be directly available here, geocoding is primary
                    "address": top_candidate.get('name'), # Or other fields if present
                    "source_format": "semanticSegments"
                })
        elif 'activity' in segment:
            activity_data = segment['activity']
            distance_meters = activity_data.get('distanceMeters')

            if isinstance(distance_meters, (int, float)):
                start_coords_str = activity_data.get('start', {}).get('latLng')
                end_coords_str = activity_data.get('end', {}).get('latLng')
                start_coords = parse_degree_lat_lon_string(start_coords_str)
                end_coords = parse_degree_lat_lon_string(end_coords_str)

                parsed_travels.append({
                    "type": "travel",
                    "startTimestamp": start_ts,
                    "endTimestamp": end_ts,
                    "distance_km": distance_meters / 1000.0,
                    "activityType": activity_data.get('topCandidate', {}).get('type'),
                    "startLat": start_coords[0] if start_coords else None,
                    "startLon": start_coords[1] if start_coords else None,
                    "endLat": end_coords[0] if end_coords else None,
                    "endLon": end_coords[1] if end_coords else None,
                    "source_format": "semanticSegments"
                })
        elif 'timelinePath' in segment:
            # This is a fallback if no 'activity' segment with distance covers this period
            # Check if this time range is already covered by a travel segment from 'activity'
            is_covered = False
            for pt in parsed_travels:
                if pt['source_format'] == "semanticSegments" and \
                   max(pt['startTimestamp'], start_ts) < min(pt['endTimestamp'], end_ts): # Overlap
                    if 'distance_km' in pt and pt.get('activityType'): # Check if it came from 'activity'
                        is_covered = True
                        break
            if not is_covered:
                distance_km_path = calculate_distance_from_timeline_path(segment['timelinePath'])
                if distance_km_path > 0:
                    parsed_travels.append({
                        "type": "travel",
                        "startTimestamp": start_ts,
                        "endTimestamp": end_ts,
                        "distance_km": distance_km_path,
                        "activityType": "PATH_BASED_TRAVEL", # Generic type
                        # start/end lat/lon could be derived from first/last path point
                        "source_format": "semanticSegments_timelinePath"
                    })
    return parsed_visits, parsed_travels


def load_and_normalize_timeline_data(
    timeline_json_path: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Loads raw timeline data and normalizes it into visits and travels."""
    print(f"\nLoading Timeline data from: {timeline_json_path}...")
    try:
        with open(timeline_json_path, 'r', encoding='utf-8') as f:
            raw_timeline_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Timeline JSON file not found at {timeline_json_path}")
        return [], []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {timeline_json_path}")
        return [], []

    all_visits: List[Dict[str, Any]] = []
    all_travels: List[Dict[str, Any]] = []

    timeline_objects = raw_timeline_data.get('timelineObjects')
    if timeline_objects and isinstance(timeline_objects, list) and len(timeline_objects) > 0:
        print("Processing using 'timelineObjects' structure...")
        all_visits, all_travels = parse_timeline_objects(timeline_objects)
    else:
        semantic_segments = raw_timeline_data.get('semanticSegments')
        if semantic_segments and isinstance(semantic_segments, list) and len(semantic_segments) > 0:
            print("No 'timelineObjects' found or empty. Processing using 'semanticSegments' structure...")
            all_visits, all_travels = parse_semantic_segments(semantic_segments)
        else:
            print("Error: No 'timelineObjects' or 'semanticSegments' found in the JSON file, or they are empty.")
            return [], []
            
    # Sort by start time once
    all_visits.sort(key=lambda x: x['startTimestamp'] if x['startTimestamp'] else datetime.min)
    all_travels.sort(key=lambda x: x['startTimestamp'] if x['startTimestamp'] else datetime.min)
    
    print(f"Loaded and parsed {len(all_visits)} visits and {len(all_travels)} travel segments.")
    return all_visits, all_travels


# --- Core Logic ---
def analyze_daily_trips( # Renamed from process_timeline_data
    all_parsed_visits: List[Dict[str, Any]],
    all_parsed_travels: List[Dict[str, Any]],
    home_coords: Tuple[float, float],
    home_full_address: str,
    work_locations_data: List[Dict[str, Any]],
    start_date_obj: date,
    end_date_obj: date,
    proximity_radius_m: float
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Analyzes normalized timeline data to find qualifying trips.
    Returns a list of trip details and the total kilometers for qualifying trips.
    """
    qualified_trips_details = []
    total_kms_qualifying_trips = 0.0

    current_date_iter = start_date_obj
    while current_date_iter <= end_date_obj:
        day_str = current_date_iter.strftime('%Y-%m-%d')
        
        # Filter events for the current day (local time of the timestamp)
        # Timestamps are timezone-aware; .date() gives the date in that timezone.
        current_day_visits = [
            v for v in all_parsed_visits 
            if v['startTimestamp'] and v['startTimestamp'].date() == current_date_iter
        ]
        current_day_travels = [
            t for t in all_parsed_travels 
            if t['startTimestamp'] and t['startTimestamp'].date() == current_date_iter
        ]

        # Combine and sort all events for the day
        # Ensure all events have 'type' and valid 'startTimestamp'
        day_events_valid = [e for e in (current_day_visits + current_day_travels) if e.get('type') and e.get('startTimestamp')]
        current_day_events = sorted(day_events_valid, key=lambda x: x['startTimestamp'])
        
        if not current_day_events:
            current_date_iter += timedelta(days=1)
            continue
            
        # State for the day
        found_home_morning = None
        found_work_visit = None
        found_work_location_details = None
        activity_to_work_obj = None
        found_home_evening = None
        activity_from_work_obj = None

        # 1. Look for initial home visit
        # Iterate through events. If it's a visit and at home, it's found_home_morning.
        # Then, look for a subsequent travel segment, then a work visit, etc.
        
        event_idx = 0
        while event_idx < len(current_day_events):
            # Reset for each potential start from home
            found_home_morning = None
            found_work_visit = None
            found_work_location_details = None
            activity_to_work_obj = None
            found_home_evening = None
            activity_from_work_obj = None
            
            # A. Find Home Visit in Morning
            current_event = current_day_events[event_idx]
            if current_event['type'] == 'visit' and \
               is_near((current_event['lat'], current_event['lon']), home_coords, proximity_radius_m) and \
               current_event['startTimestamp'].time() < time(13,0): # Heuristic: before 1 PM
                found_home_morning = current_event
            else:
                event_idx += 1
                continue # Not a morning home visit, try next event as potential start

            # B. Find Travel to Work & Work Visit
            # Search from event after found_home_morning
            temp_idx = event_idx + 1
            while temp_idx < len(current_day_events) and not found_work_visit:
                travel_candidate = current_day_events[temp_idx]
                if travel_candidate['type'] == 'travel' and \
                   travel_candidate['startTimestamp'] >= found_home_morning['endTimestamp']:
                    # Now look for a work visit immediately after this travel
                    if temp_idx + 1 < len(current_day_events):
                        visit_candidate = current_day_events[temp_idx + 1]
                        if visit_candidate['type'] == 'visit' and \
                           abs((travel_candidate['endTimestamp'] - visit_candidate['startTimestamp']).total_seconds()) < 600: # Within 10 mins
                            for work_loc in work_locations_data:
                                if is_near((visit_candidate['lat'], visit_candidate['lon']), work_loc['coords'], proximity_radius_m):
                                    activity_to_work_obj = travel_candidate
                                    found_work_visit = visit_candidate
                                    found_work_location_details = work_loc
                                    event_idx = temp_idx + 1 # Advance main index past this work visit
                                    break # Found work visit
                        if found_work_visit: break
                temp_idx += 1
            
            if not (found_work_visit and activity_to_work_obj):
                event_idx +=1 # Did not complete H->W, advance main index from original home_morning point
                continue

            # C. Find Travel from Work & Home Visit Evening
            temp_idx = event_idx + 1 # Start searching after the found_work_visit
            while temp_idx < len(current_day_events) and not found_home_evening:
                travel_candidate_home = current_day_events[temp_idx]
                if travel_candidate_home['type'] == 'travel' and \
                   travel_candidate_home['startTimestamp'] >= found_work_visit['endTimestamp']:
                    if temp_idx + 1 < len(current_day_events):
                        return_home_candidate = current_day_events[temp_idx + 1]
                        if return_home_candidate['type'] == 'visit' and \
                           abs((travel_candidate_home['endTimestamp'] - return_home_candidate['startTimestamp']).total_seconds()) < 600 and \
                           is_near((return_home_candidate['lat'], return_home_candidate['lon']), home_coords, proximity_radius_m):
                            activity_from_work_obj = travel_candidate_home
                            found_home_evening = return_home_candidate
                            event_idx = temp_idx + 1 # Advance main index past this successful HWH sequence
                            break
                temp_idx += 1

            if found_home_morning and found_work_visit and activity_to_work_obj and \
               found_home_evening and activity_from_work_obj:
                
                dist_to_work_km = activity_to_work_obj.get('distance_km', 0.0)
                dist_from_work_km = activity_from_work_obj.get('distance_km', 0.0)

                if dist_to_work_km > 0 and dist_from_work_km > 0: # Ensure valid distances
                    daily_total_km = dist_to_work_km + dist_from_work_km
                    trip_data = {
                        "Date": current_date_iter.strftime('%Y-%m-%d'),
                        "Work Location Visited (Query)": found_work_location_details['name_query'],
                        "Work Location Visited (Geocoded)": found_work_location_details['name_geocoded'],
                        "Distance to Work (km)": round(dist_to_work_km, 2),
                        "Distance from Work (km)": round(dist_from_work_km, 2),
                        "Total Distance (km)": round(daily_total_km, 2),
                        "Home Address (Geocoded)": home_full_address,
                        "Source Format": f"{found_home_morning.get('source_format', 'N/A')}" # Indicate source
                    }
                    qualified_trips_details.append(trip_data)
                    total_kms_qualifying_trips += daily_total_km
                    print(f"  ✓ Day {day_str}: Home -> '{found_work_location_details['name_query']}' -> Home. Dist: {daily_total_km:.2f} km. Source: {trip_data['Source Format']}")
                    # Successfully processed a HWH trip for this day, break from daily event loop
                    # to avoid finding multiple HWH trips on the same day with this simple loop
                    break # Found one HWH trip for the day, move to next day
            else: # HWH not completed from this home_morning, try next event as potential start
                event_idx = current_day_events.index(found_home_morning) + 1 if found_home_morning in current_day_events else event_idx + 1


        current_date_iter += timedelta(days=1)
    
    return qualified_trips_details, total_kms_qualifying_trips


def write_to_excel(results: List[Dict[str, Any]], filename: str) -> None:
    """Writes the results to an XLSX file."""
    if not results:
        print("No results to write to Excel.")
        return

    df = pd.DataFrame(results)
    try:
        df.to_excel(filename, index=False, engine='openpyxl')
        print(f"\nResults successfully written to {filename}")
    except Exception as e:
        print(f"Error writing to Excel file {filename}: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze Google Maps Timeline data for home-to-work-and-back trips.")
    parser.add_argument("--home_address", required=True, help="Your home address string.")
    parser.add_argument("--work_destinations", nargs='+', required=True, help="List of work destination address strings.")
    parser.add_argument("--start_date", required=True, help="Start date for analysis (YYYY-MM-DD).")
    parser.add_argument("--end_date", required=True, help="End date for analysis (YYYY-MM-DD).")
    parser.add_argument("--timeline_json", required=True, help="Path to your Google Timeline JSON file.")
    parser.add_argument("--api_key", required=True, help="Your Google Maps Geocoding API key.")
    parser.add_argument("--output_xlsx", default="travel_report.xlsx", help="Output XLSX file name.")
    parser.add_argument("--proximity_radius_m", type=int, default=DEFAULT_PROXIMITY_RADIUS_METERS,
                        help=f"Proximity radius in meters to match locations (default: {DEFAULT_PROXIMITY_RADIUS_METERS}m).")

    args = parser.parse_args()

    if not os.path.exists(args.timeline_json):
        print(f"Error: Timeline JSON file not found at '{args.timeline_json}'")
        exit(1)
        
    print("Starting travel analysis...")
    # ... (print args)

    gmaps = googlemaps.Client(key=args.api_key)

    home_options = geocode_address(gmaps, args.home_address)
    selected_home_geo = select_geocoded_location(home_options, f"Home: '{args.home_address}'")
    if not selected_home_geo:
        print(f"Could not geocode home address: {args.home_address}. Exiting.")
        exit(1)
    home_coords_val = (
        selected_home_geo['geometry']['location']['lat'],
        selected_home_geo['geometry']['location']['lng']
    )
    home_full_address_val = selected_home_geo['formatted_address']

    work_locations_data_val = []
    for work_addr_str in args.work_destinations:
        work_options = geocode_address(gmaps, work_addr_str)
        selected_work_geo = select_geocoded_location(work_options, f"Work: '{work_addr_str}'")
        if selected_work_geo:
            work_locations_data_val.append({
                "name_query": work_addr_str,
                "name_geocoded": selected_work_geo['formatted_address'],
                "coords": (
                    selected_work_geo['geometry']['location']['lat'],
                    selected_work_geo['geometry']['location']['lng']
                )
            })
        else:
            print(f"Warning: Could not geocode work address: {work_addr_str}. Skipping it.")

    if not work_locations_data_val:
        print("No work locations could be geocoded. Exiting.")
        exit(1)

    try:
        start_dt_obj_val = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_dt_obj_val = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    except ValueError:
        print("Error: Invalid date format for start/end date. Please use YYYY-MM-DD.")
        exit(1)

    all_parsed_visits_val, all_parsed_travels_val = load_and_normalize_timeline_data(args.timeline_json)

    if not all_parsed_visits_val and not all_parsed_travels_val:
        print("Could not extract any visit or travel data from the timeline file.")
        exit(1)

    print(f"\nProcessing data from {args.start_date} to {args.end_date}...")
    print(f"Using proximity radius: {args.proximity_radius_m} meters.")
    
    qualified_trips, total_kms = analyze_daily_trips(
        all_parsed_visits=all_parsed_visits_val,
        all_parsed_travels=all_parsed_travels_val,
        home_coords=home_coords_val,
        home_full_address=home_full_address_val,
        work_locations_data=work_locations_data_val,
        start_date_obj=start_dt_obj_val,
        end_date_obj=end_dt_obj_val,
        proximity_radius_m=float(args.proximity_radius_m)
    )

    if qualified_trips:
        write_to_excel(qualified_trips, args.output_xlsx)
        print(f"\nSummary:")
        print(f"Found {len(qualified_trips)} days matching the 'Home -> Work -> Home' pattern.")
        print(f"Total kilometers driven for these trips: {total_kms:.2f} km")
    else:
        print("\nNo qualifying trips found for the given criteria.")

    print("\nAnalysis complete.")