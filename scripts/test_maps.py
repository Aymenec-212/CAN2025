import asyncio
import sys
sys.path.append(".")

from app.agents.tools.maps_tools import tool_get_stadium_details, tool_get_directions

async def main():
    print("--- 1. Testing DB-First Stadium Details ---")
    # 'Prince Moulay Abdellah Stadium' is in our Seed
    details = await tool_get_stadium_details("Prince Moulay Abdellah")
    print(f"Source: {details.get('source')} | Name: {details.get('name')}")
    # Expect: Source: db

    print("\n--- 2. Testing Fallback Stadium Details ---")
    # Random name not in DB
    details_fb = await tool_get_stadium_details("Marrakech Stadium")
    print(f"Source: {details_fb.get('source')} | Name: {details_fb.get('name')}")
    # Expect: Source: google_maps (if key valid) or error

    print("\n--- 3. Testing Directions ---")
    route = await tool_get_directions(origin="Rabat Agdal Station", stadium_name="Stade Mohammed V")
    if "route" in route:
        print(f"Duration: {route['route']['duration']}")
    else:
        print(f"Error: {route}")

if __name__ == "__main__":
    asyncio.run(main())