"""
Eksempel script: Find en simpel cykelrute mellem to adresser i Aarhus.
"""

import sys
from pathlib import Path

# Tilføj projekt root til path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.route_finder import RouteFinder


def main():
    """Eksempel: Find rute mellem Aarhus Hovedbanegård og Aarhus Universitet."""
    
    print("🚴‍♂️ Aarhus Best Cycling Routes - Eksempel")
    print("=" * 50)
    
    # Opret RouteFinder
    finder = RouteFinder()
    
    # Definer start og slut adresser
    start_address = "Aarhus Hovedbanegård, 8000 Aarhus C"
    end_address = "Aarhus Universitet, 8000 Aarhus C"
    
    print(f"\n📍 Start: {start_address}")
    print(f"📍 Slut: {end_address}")
    print("\n🔍 Finder rute...")
    
    # Find rute
    route = finder.find_route(
        start_address=start_address,
        end_address=end_address,
        route_name="Aarhus Hovedbanegård → Aarhus Universitet",
        check_weather=True
    )
    
    if not route:
        print("❌ Kunne ikke finde rute")
        return
    
    # Vis rute information
    print("\n✅ Rute fundet!")
    print(f"   Distance: {route['distance']:.2f} km")
    print(f"   Varighed: {route['duration']:.1f} minutter")
    
    if route.get('weather'):
        weather = route['weather']
        print(f"\n🌤️  Vejrdata:")
        print(f"   Beskrivelse: {weather.get('description', 'N/A')}")
        print(f"   Temperatur: {weather.get('temperature', 'N/A')}°C")
        print(f"   Vind: {weather.get('wind_speed', 'N/A')} m/s")
        print(f"   Regn: {weather.get('rain', 0)} mm")
        
        if route.get('weather_good') is not None:
            status = "✅ Godt vejr til cykling" if route['weather_good'] else "⚠️  Dårligt vejr"
            print(f"   Status: {status}")
    
    # Gem rute
    print("\n💾 Gemmer rute...")
    files = finder.save_route(route, "aarhus_banegard_til_universitet")
    
    print(f"\n✅ Rute gemt!")
    print(f"   GPX fil: {files['gpx']}")
    print(f"   Kort: {files['map']}")
    print(f"\n💡 Tip: Åbn HTML filen i din browser for at se ruten på kort!")


if __name__ == "__main__":
    main()


