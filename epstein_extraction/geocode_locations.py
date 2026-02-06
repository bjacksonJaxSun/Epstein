"""
Geocode locations in the database using OpenStreetMap Nominatim.
This script populates latitude/longitude for locations that have address information.
"""

import os
import sys
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Rate limiting for Nominatim (max 1 request per second)
REQUEST_DELAY = 1.1

# Known locations with verified coordinates and country
# Format: (latitude, longitude, country, city)
KNOWN_LOCATIONS = {
    # Key Epstein properties
    "little st. james": (18.2998, -64.8254, "US Virgin Islands", "St. Thomas"),
    "little saint james": (18.2998, -64.8254, "US Virgin Islands", "St. Thomas"),
    "little st james": (18.2998, -64.8254, "US Virgin Islands", "St. Thomas"),
    "epstein island": (18.2998, -64.8254, "US Virgin Islands", "St. Thomas"),
    "the island": (18.2998, -64.8254, "US Virgin Islands", "St. Thomas"),
    "great st. james": (18.3147, -64.8399, "US Virgin Islands", "St. Thomas"),
    "great saint james": (18.3147, -64.8399, "US Virgin Islands", "St. Thomas"),
    "9 east 71st street": (40.7720, -73.9630, "United States", "New York"),
    "9 e 71st": (40.7720, -73.9630, "United States", "New York"),
    "9 e. 71st": (40.7720, -73.9630, "United States", "New York"),
    "71st street": (40.7720, -73.9630, "United States", "New York"),
    "the townhouse": (40.7720, -73.9630, "United States", "New York"),
    "358 el brillo way": (26.6887, -80.0369, "United States", "Palm Beach"),
    "el brillo way": (26.6887, -80.0369, "United States", "Palm Beach"),
    "palm beach house": (26.6887, -80.0369, "United States", "Palm Beach"),
    "palm beach mansion": (26.6887, -80.0369, "United States", "Palm Beach"),
    "zorro ranch": (35.1055, -105.9569, "United States", "Stanley"),
    "stanley, new mexico": (35.1055, -105.9569, "United States", "Stanley"),
    "new mexico ranch": (35.1055, -105.9569, "United States", "Stanley"),
    "avenue foch": (48.8721, 2.2874, "France", "Paris"),
    "22 avenue foch": (48.8721, 2.2874, "France", "Paris"),
    "paris apartment": (48.8721, 2.2874, "France", "Paris"),

    # Detention facilities
    "metropolitan correctional center": (40.7127, -74.0030, "United States", "New York"),
    "mcc new york": (40.7127, -74.0030, "United States", "New York"),
    "mcc": (40.7127, -74.0030, "United States", "New York"),
    "federal detention center": (40.7127, -74.0030, "United States", "New York"),

    # Airports
    "teterboro airport": (40.8501, -74.0608, "United States", "Teterboro"),
    "teterboro": (40.8501, -74.0608, "United States", "Teterboro"),
    "palm beach international": (26.6832, -80.0956, "United States", "West Palm Beach"),
    "jfk": (40.6413, -73.7781, "United States", "New York"),
    "laguardia": (40.7769, -73.8740, "United States", "New York"),
    "cyril e. king": (18.3373, -64.9735, "US Virgin Islands", "St. Thomas"),
    "st. thomas airport": (18.3373, -64.9735, "US Virgin Islands", "St. Thomas"),

    # Cities/Areas
    "new york": (40.7128, -74.0060, "United States", "New York"),
    "new york city": (40.7128, -74.0060, "United States", "New York"),
    "manhattan": (40.7831, -73.9712, "United States", "New York"),
    "palm beach": (26.7056, -80.0364, "United States", "Palm Beach"),
    "west palm beach": (26.7153, -80.0534, "United States", "West Palm Beach"),
    "miami": (25.7617, -80.1918, "United States", "Miami"),
    "miami beach": (25.7907, -80.1300, "United States", "Miami Beach"),
    "paris": (48.8566, 2.3522, "France", "Paris"),
    "london": (51.5074, -0.1278, "United Kingdom", "London"),
    "los angeles": (34.0522, -118.2437, "United States", "Los Angeles"),
    "santa fe": (35.6870, -105.9378, "United States", "Santa Fe"),
    "albuquerque": (35.0844, -106.6504, "United States", "Albuquerque"),

    # US Virgin Islands
    "virgin islands": (18.3358, -64.8963, "US Virgin Islands", None),
    "us virgin islands": (18.3358, -64.8963, "US Virgin Islands", None),
    "u.s. virgin islands": (18.3358, -64.8963, "US Virgin Islands", None),
    "st. thomas": (18.3381, -64.8941, "US Virgin Islands", "St. Thomas"),
    "saint thomas": (18.3381, -64.8941, "US Virgin Islands", "St. Thomas"),
    "st. croix": (17.7289, -64.7348, "US Virgin Islands", "St. Croix"),
    "saint croix": (17.7289, -64.7348, "US Virgin Islands", "St. Croix"),
    "charlotte amalie": (18.3419, -64.9307, "US Virgin Islands", "Charlotte Amalie"),

    # Other relevant locations
    "mar-a-lago": (26.6776, -80.0365, "United States", "Palm Beach"),
    "buckingham palace": (51.5014, -0.1419, "United Kingdom", "London"),
    "windsor castle": (51.4839, -0.6044, "United Kingdom", "Windsor"),
    "modeling agency": (40.7589, -73.9851, "United States", "New York"),
    "mc2": (40.7589, -73.9851, "United States", "New York"),

    # Maxwell properties
    "belgravia": (51.4990, -0.1526, "United Kingdom", "London"),
    "oxford": (51.7520, -1.2577, "United Kingdom", "Oxford"),
}

# Patterns that indicate non-geocodable locations
SKIP_PATTERNS = [
    "general population", "special housing", "shu", "unit", "floor",
    "cell", "range", "chapel", "lobby", "rear-gate", "front gate",
    "health service", "beekman hospital", "conference room", "office",
    "bedroom", "bathroom", "kitchen", "pool", "dock", "airplane",
    "lolita express", "gulfstream", "boeing", "helicopter",
]


def get_db_connection():
    """Create database connection."""
    db_path = os.environ.get(
        "DATABASE_URL",
        os.path.join(os.path.dirname(__file__), "..", "extraction_output", "epstein_documents.db")
    )

    if not db_path.startswith("sqlite"):
        db_path = f"sqlite:///{db_path}"

    engine = create_engine(db_path)
    return engine


def geocode_with_nominatim(address_parts):
    """
    Geocode an address using Nominatim.
    Returns (lat, lng) or None if not found.
    """
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    except ImportError:
        print("geopy not installed. Install with: pip install geopy")
        return None

    geolocator = Nominatim(user_agent="epstein_dashboard_geocoder")

    # Build search query from address parts
    query_parts = [p for p in address_parts if p]
    if not query_parts:
        return None

    query = ", ".join(query_parts)

    try:
        time.sleep(REQUEST_DELAY)  # Rate limiting
        location = geolocator.geocode(query, timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"  Geocoding error for '{query}': {e}")
    except Exception as e:
        print(f"  Unexpected error geocoding '{query}': {e}")

    return None


def should_skip_location(location_name):
    """Check if location should be skipped (rooms, units, etc.)."""
    if not location_name:
        return True

    name_lower = location_name.lower().strip()

    for pattern in SKIP_PATTERNS:
        if pattern in name_lower:
            return True

    # Skip very short names or numeric-only names
    if len(name_lower) < 3:
        return True

    # Skip if it looks like a room/cell number
    if name_lower.replace("-", "").replace(" ", "").isalnum() and any(c.isdigit() for c in name_lower):
        if len(name_lower) < 10:
            return True

    return False


def check_known_locations(location_name, city=None, country=None):
    """Check if location matches a known location.
    Returns (lat, lng, country, city) or None.
    """
    if not location_name:
        return None

    name_lower = location_name.lower().strip()

    # Direct match
    if name_lower in KNOWN_LOCATIONS:
        return KNOWN_LOCATIONS[name_lower]

    # Partial match - be more careful with shorter known names
    for known_name, data in KNOWN_LOCATIONS.items():
        if len(known_name) >= 5:  # Only match if known name is reasonably long
            if known_name in name_lower:
                return data

    # Check city/country
    if city:
        city_lower = city.lower()
        if city_lower in KNOWN_LOCATIONS:
            return KNOWN_LOCATIONS[city_lower]

    if country:
        country_lower = country.lower()
        if country_lower in KNOWN_LOCATIONS:
            return KNOWN_LOCATIONS[country_lower]

    return None


def geocode_locations(dry_run=False, limit=None):
    """
    Geocode all locations that don't have coordinates.
    """
    engine = get_db_connection()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get locations without coordinates
        query = """
            SELECT location_id, location_name, street_address, city, state_province, country
            FROM locations
            WHERE latitude IS NULL OR longitude IS NULL
            ORDER BY location_id
        """
        if limit:
            query += f" LIMIT {limit}"

        result = session.execute(text(query))
        locations = result.fetchall()

        print(f"Found {len(locations)} locations without coordinates")

        geocoded_count = 0
        known_count = 0
        failed_count = 0

        skipped_count = 0

        for loc in locations:
            loc_id, name, address, city, state, country = loc

            # Skip non-geocodable locations (rooms, units, etc.)
            if should_skip_location(name):
                skipped_count += 1
                continue

            print(f"\n[{loc_id}] {name}")
            if city or state or country:
                print(f"    Address: {', '.join(filter(None, [address, city, state, country]))}")

            # First, check known locations
            known_data = check_known_locations(name, city, country)
            if known_data:
                lat, lng, known_country, known_city = known_data
                print(f"    -> Known location: ({lat:.4f}, {lng:.4f}) - {known_city or ''}, {known_country or ''}")
                known_count += 1
                if not dry_run:
                    session.execute(
                        text("UPDATE locations SET latitude = :lat, longitude = :lng, country = :country, city = :city WHERE location_id = :id"),
                        {"lat": lat, "lng": lng, "country": known_country, "city": known_city, "id": loc_id}
                    )
                continue

            # Skip if no address information
            address_parts = [p for p in [address, city, state, country] if p]
            if not address_parts and name:
                # Try geocoding just the name
                address_parts = [name]

            if not address_parts:
                print("    -> No address information, skipping")
                failed_count += 1
                continue

            # Try geocoding
            coords = geocode_with_nominatim(address_parts)
            if coords:
                print(f"    -> Geocoded: ({coords[0]:.4f}, {coords[1]:.4f})")
                geocoded_count += 1
                if not dry_run:
                    session.execute(
                        text("UPDATE locations SET latitude = :lat, longitude = :lng WHERE location_id = :id"),
                        {"lat": coords[0], "lng": coords[1], "id": loc_id}
                    )
            else:
                print("    -> Could not geocode")
                failed_count += 1

        if not dry_run:
            session.commit()

        print(f"\n\nSummary:")
        print(f"  Known locations matched: {known_count}")
        print(f"  Geocoded via Nominatim: {geocoded_count}")
        print(f"  Skipped (rooms/units): {skipped_count}")
        print(f"  Failed to geocode: {failed_count}")
        print(f"  Total processed: {len(locations)}")

        if dry_run:
            print("\n(Dry run - no changes made to database)")

    finally:
        session.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Geocode locations in the database")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update the database")
    parser.add_argument("--limit", type=int, help="Limit number of locations to process")
    args = parser.parse_args()

    geocode_locations(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
