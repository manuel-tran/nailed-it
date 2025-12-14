import requests
from geopy.distance import geodesic

# 1. Your Location
current_lat = 48.12364444691372
current_lon = 11.600215507421492


def find_nearest_store_osm(lat, lon):
    # Overpass API URL (Public instance)
    overpass_url = "http://overpass-api.de/api/interpreter"

    # 2. Construct the Query
    # We ask for nodes of type "shop=supermarket" or "shop=convenience"
    # around 1000 meters of your location.
    overpass_query = f"""
    [out:json];
    (
      node["shop"="supermarket"](around:1000, {lat}, {lon});
      node["shop"="convenience"](around:1000, {lat}, {lon});
    );
    out body;
    """

    print("Querying OpenStreetMap...")
    try:
        response = requests.get(overpass_url, params={'data': overpass_query})
        data = response.json()

        stores = []

        # 3. Parse and Calculate Distance
        for element in data['elements']:
            name = element.get('tags', {}).get('name', 'Unnamed Store')
            store_lat = element['lat']
            store_lon = element['lon']

            # Calculate exact distance in meters
            dist = geodesic((lat, lon), (store_lat, store_lon)).meters

            stores.append(
                {
                    "name": name,
                    "distance": dist,
                    "lat": store_lat,
                    "lon": store_lon
                }
            )

        # 4. Sort by nearest
        if stores:
            stores.sort(key=lambda x: x['distance'])
            nearest = stores[0]

            print(f"\n--- Nearest Store Found (Free!) ---")
            print(f"Name:     {nearest['name']}")
            print(f"Distance: {int(nearest['distance'])} meters")
            print(f"Location: {nearest['lat']}, {nearest['lon']}")
            print(
                f"Link:     https://www.openstreetmap.org/node/{data['elements'][0]['id']}"
            )
        else:
            print("No stores found within 1000m.")

    except Exception as e:
        print(f"Error: {e}")


# Run it
find_nearest_store_osm(current_lat, current_lon)
