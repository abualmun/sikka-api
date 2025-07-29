import gpxpy
import sys
import os
import csv
import zipfile
from datetime import timedelta, datetime
from shapely.geometry import LineString
import geopy.distance
from scipy.spatial import KDTree
import shutil

if len(sys.argv) < 2:
    print("Usage: python3 main.py <directory_path>")
    sys.exit(1)

directory_path = sys.argv[1]

if not os.path.isdir(directory_path):
    print(f"Error: Directory '{directory_path}' does not exist.")
    sys.exit(1)

gpx_files = [f for f in os.listdir(directory_path) if f.lower().endswith('.gpx')]
if not gpx_files:
    print(f"No GPX files found in directory '{directory_path}'")
    sys.exit(1)

print(f"Found {len(gpx_files)} GPX files: {', '.join(gpx_files)}")

agency_name = "Void"
agency_url = "https://abualmun.github.io/portfolio.io/"
agency_timezone = "Africa/Khartoum"

speed_kmh = float(input("Average Speed (km/h): ").strip())
stop_dist = float(input("Distance Between Stops (meters): ").strip())
frequency_headway = int(input("Frequency Headway in seconds (e.g., 600 for 10 mins): ").strip())


def process_gpx_file(gpx_file_path):
    with open(gpx_file_path, 'r') as f:
        gpx = gpxpy.parse(f)

    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append((point.longitude, point.latitude))

    return points


def geodesic_length(coords):
    total = 0
    for i in range(len(coords) - 1):
        total += geopy.distance.geodesic(coords[i][::-1], coords[i + 1][::-1]).meters
    return total


def generate_stops_and_times(points, stop_dist):
    line = LineString(points)
    total_meters = geodesic_length(points)
    num_stops = max(int(total_meters // stop_dist), 1)

    interpolated = []
    dist_step = line.length / num_stops
    for i in range(num_stops + 1):
        point = line.interpolate(dist_step * i)
        interpolated.append((point.x, point.y))

    return interpolated


def calculate_travel_times(stops_coords, speed_kmh):
    """Calculate cumulative travel times between stops"""
    times = [0]  # Start at 0 seconds
    speed_ms = speed_kmh * 1000 / 3600  # Convert km/h to m/s
    
    for i in range(len(stops_coords) - 1):
        # Calculate distance between consecutive stops
        distance = geopy.distance.geodesic(
            (stops_coords[i][1], stops_coords[i][0]),  # lat, lon
            (stops_coords[i + 1][1], stops_coords[i + 1][0])
        ).meters
        
        # Calculate travel time and add to cumulative time
        travel_time = distance / speed_ms
        times.append(times[-1] + travel_time)
    
    return times


def seconds_to_gtfs_time(seconds):
    """Convert seconds to GTFS time format (HH:MM:SS)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# Clean up and create temp directory
temp_dir = "gtfs_temp"
if os.path.exists(temp_dir):
    shutil.rmtree(temp_dir)
os.makedirs(temp_dir, exist_ok=True)

all_stops = []
stop_coords = []
stop_id_map = {}
stop_counter = 1
routes_data = []
all_shapes = []
all_stop_times = []

for idx, gpx_filename in enumerate(gpx_files, start=1):
    gpx_file_path = os.path.join(directory_path, gpx_filename)
    route_name = os.path.splitext(gpx_filename)[0]
    print(f"Processing {gpx_filename}...")

    try:
        points = process_gpx_file(gpx_file_path)
        interpolated_stops = generate_stops_and_times(points, stop_dist)

        shape_id = idx
        route_stops = []
        route_stop_coords = []
        
        # Generate stops for this route
        for coord in interpolated_stops:
            key = (round(coord[1], 5), round(coord[0], 5))
            if key not in stop_id_map:
                stop_id = stop_counter
                stop_counter += 1
                stop_id_map[key] = stop_id
                all_stops.append({
                    'stop_id': stop_id,
                    'stop_name': f'Stop {stop_id}',
                    'stop_lat': coord[1],
                    'stop_lon': coord[0]
                })
                stop_coords.append([coord[1], coord[0]])
            else:
                stop_id = stop_id_map[key]

            route_stops.append(stop_id)
            route_stop_coords.append((coord[0], coord[1]))  # lon, lat for distance calc

        # Calculate travel times for this route
        travel_times = calculate_travel_times(route_stop_coords, speed_kmh)
        
        # Generate stop_times for this trip
        base_start_time = 6 * 3600  # 06:00:00 in seconds
        for stop_sequence, (stop_id, travel_time) in enumerate(zip(route_stops, travel_times)):
            arrival_time = base_start_time + travel_time
            departure_time = arrival_time  # Same as arrival for simplicity
            
            all_stop_times.append({
                'trip_id': idx,
                'arrival_time': seconds_to_gtfs_time(arrival_time),
                'departure_time': seconds_to_gtfs_time(departure_time),
                'stop_id': stop_id,
                'stop_sequence': stop_sequence + 1
            })

        # Generate shapes
        for shape_idx, coord in enumerate(points):
            all_shapes.append({
                'shape_id': shape_id,
                'shape_pt_lat': coord[1],
                'shape_pt_lon': coord[0],
                'shape_pt_sequence': shape_idx + 1
            })

        routes_data.append({
            'route_id': idx,
            'route_name': route_name,
            'shape_id': shape_id,
            'stops': route_stops
        })

    except Exception as e:
        print(f"Error processing {gpx_filename}: {e}")
        continue

print("Generating GTFS files...")

def write_csv(filename, headers, rows):
    with open(os.path.join(temp_dir, filename), 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)

# Generate agency.txt
write_csv('agency.txt', ['agency_id', 'agency_name', 'agency_url', 'agency_timezone'], [
    [1, agency_name, agency_url, agency_timezone]
])

# Generate stops.txt
write_csv('stops.txt', ['stop_id', 'stop_name', 'stop_lat', 'stop_lon'], [
    [stop['stop_id'], stop['stop_name'], stop['stop_lat'], stop['stop_lon']] for stop in all_stops
])

# Generate routes.txt
write_csv('routes.txt', ['route_id', 'agency_id', 'route_short_name', 'route_long_name', 'route_type'], [
    [route['route_id'], 1, route['route_name'], route['route_name'], 3] for route in routes_data
])

# Generate trips.txt
write_csv('trips.txt', ['route_id', 'service_id', 'trip_id', 'shape_id'], [
    [route['route_id'], 1, route['route_id'], route['shape_id']] for route in routes_data
])

# Generate stop_times.txt (REQUIRED FILE that was missing)
write_csv('stop_times.txt', ['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence'], [
    [st['trip_id'], st['arrival_time'], st['departure_time'], st['stop_id'], st['stop_sequence']] 
    for st in all_stop_times
])

# Generate frequencies.txt
write_csv('frequencies.txt', ['trip_id', 'start_time', 'end_time', 'headway_secs'], [
    [route['route_id'], '06:00:00', '22:00:00', frequency_headway] for route in routes_data
])

# Generate calendar.txt (Fixed formatting)
write_csv('calendar.txt', ['service_id', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'start_date', 'end_date'], [
    [1, 1, 1, 1, 1, 1, 1, 1, '20250720', '20251231']
])

# Generate shapes.txt
write_csv('shapes.txt', ['shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence'], [
    [shape['shape_id'], shape['shape_pt_lat'], shape['shape_pt_lon'], shape['shape_pt_sequence']] for shape in all_shapes
])

print("Generating transfers.txt with KDTree...")
transfers = []
if len(stop_coords) > 1:  # Only generate transfers if we have multiple stops
    tree = KDTree(stop_coords)
    for i, (lat1, lon1) in enumerate(stop_coords):
        nearby_indices = tree.query_ball_point([lat1, lon1], r=0.0003)  # ~30 meters
        for j in nearby_indices:
            if i != j and all_stops[i]['stop_id'] != all_stops[j]['stop_id']:
                transfers.append((all_stops[i]['stop_id'], all_stops[j]['stop_id']))

write_csv('transfers.txt', ['from_stop_id', 'to_stop_id', 'transfer_type', 'min_transfer_time'], [
    [from_id, to_id, 0, 60] for from_id, to_id in set(transfers)
])

# Create GTFS zip file
zip_path = 'gtfs.zip'
if os.path.exists(zip_path):
    os.remove(zip_path)

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for filename in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, filename)
        zf.write(file_path, arcname=filename)

# Clean up temp directory
shutil.rmtree(temp_dir)

print(f"\n✓ Generated GTFS zip: {zip_path}")
print(f"✓ Total routes created: {len(routes_data)}")
print(f"✓ Total stops created: {len(all_stops)}")
print(f"✓ Total stop times created: {len(all_stop_times)}")
for route in routes_data:
    print(f"  - Route '{route['route_name']}': {len(route['stops'])} stops")

print(f"\nGTFS feed should now be valid for import into transit planning tools!")