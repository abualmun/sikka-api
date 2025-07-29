import gpxpy
import sys
from shapely.geometry import LineString
import geopy.distance
import csv
from datetime import timedelta

if len(sys.argv) < 2:
    print("Usage: python3 main.py input.gpx")
    sys.exit(1)

gpx_file = sys.argv[1]

# --- User Input ---
agency_name = input("Agency Name: ").strip()
agency_url = input("Agency URL (http://...): ").strip()
agency_timezone = input("Agency Timezone (e.g., Etc/GMT): ").strip()

route_short = input("Route Short Name (e.g., 10): ").strip()
route_long = input("Route Long Name (e.g., Downtown Loop): ").strip()
speed_kmh = float(input("Average Speed (km/h): ").strip())
stop_dist = float(input("Distance Between Stops (meters): ").strip())

# --- Read GPX ---
with open(gpx_file, 'r') as f:
    gpx = gpxpy.parse(f)

points = []
for track in gpx.tracks:
    for segment in track.segments:
        for point in segment.points:
            points.append((point.longitude, point.latitude))

line = LineString(points)

def geodesic_length(coords):
    total = 0
    for i in range(len(coords)-1):
        total += geopy.distance.geodesic(coords[i][::-1], coords[i+1][::-1]).meters
    return total

total_meters = geodesic_length(points)
num_stops = int(total_meters // stop_dist)

interpolated = []
dist_step = line.length / num_stops
for i in range(num_stops + 1):
    point = line.interpolate(dist_step * i)
    interpolated.append((point.x, point.y))

speed_mps = (speed_kmh * 1000) / 3600
times = [0]
for i in range(1, len(interpolated)):
    dist = geopy.distance.geodesic(interpolated[i-1][::-1], interpolated[i][::-1]).meters
    times.append(times[-1] + dist / speed_mps)

# --- Write GTFS Files ---

# agency.txt
with open('agency.txt', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['agency_id', 'agency_name', 'agency_url', 'agency_timezone'])
    writer.writerow([1, agency_name, agency_url, agency_timezone])

# stops.txt
with open('stops.txt', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['stop_id', 'stop_name', 'stop_lat', 'stop_lon'])
    for idx, coord in enumerate(interpolated, start=1):
        writer.writerow([idx, f'Stop {idx}', coord[1], coord[0]])

# routes.txt
with open('routes.txt', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['route_id', 'agency_id', 'route_short_name', 'route_long_name', 'route_type'])
    writer.writerow([1, 1, route_short, route_long, 3])

# trips.txt
with open('trips.txt', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['route_id', 'service_id', 'trip_id', 'shape_id'])
    writer.writerow([1, 1, 1, 1])

# stop_times.txt
with open('stop_times.txt', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence'])
    for idx, seconds in enumerate(times, start=1):
        hhmmss = str(timedelta(seconds=int(seconds)))
        writer.writerow([1, hhmmss, hhmmss, idx, idx])

# calendar.txt
with open('calendar.txt', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['service_id', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'start_date', 'end_date'])
    writer.writerow([1, 1, 1, 1, 1, 1, 0, 0, '20250720', '20251231'])

# shapes.txt
with open('shapes.txt', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence'])
    for idx, coord in enumerate(points, start=1):
        writer.writerow([1, coord[1], coord[0], idx])

print("\nGenerated GTFS files:")
print("agency.txt, stops.txt, routes.txt, trips.txt, stop_times.txt, calendar.txt, shapes.txt")

