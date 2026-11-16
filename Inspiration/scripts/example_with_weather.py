"""
Eksempel script: Find rute med vejrdata tjek.
"""

import sys
from pathlib import Path

# Tilføj projekt root til path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.route_finder import RouteFinder


def main():
    """Eksempel: Find rute med vejrdata tjek."""
    
    print("🚴‍♂️ Aarhus Best Cycling Routes - Vejrdata Eksempel")
    print("=" * 50)
    
    # Opret RouteFinder
    finder = RouteFinder()
    
    # Definer start og slut adresser
    start_address = "Aarhus Hovedbanegård, 8000 Aarhus C"
    end_address = "Marselisborg Slot, 8000 Aarhus C"
    
    print(f"\n📍 Start: {start_address}")
    print(f"📍 Slut: {end_address}")
    print("\n🔍 Finder rute med vejrdata tjek...")
    
    # Find rute med vejrdata
    route = finder.find_route(
        start_address=start_address,
        end_address=end_address,
        route_name="Aarhus Hovedbanegård → Marselisborg Slot",
        check_weather=True
    )
    
    if not route:
        print("❌ Kunne ikke finde rute")
        return
    
    # Vis rute information
    print("\n✅ Rute fundet!")
    print(f"   Distance: {route['distance']:.2f} km")
    print(f"   Varighed: {route['duration']:.1f} minutter")
    
    # Vis detaljeret vejrdata
    if route.get('weather'):
        weather = route['weather']
        print(f"\n🌤️  Detaljeret Vejrdata:")
        print(f"   Beskrivelse: {weather.get('description', 'N/A')}")
        print(f"   Temperatur: {weather.get('temperature', 'N/A')}°C")
        print(f"   Føles som: {weather.get('feels_like', 'N/A')}°C")
        print(f"   Vindhastighed: {weather.get('wind_speed', 'N/A')} m/s")
        print(f"   Vindretning: {weather.get('wind_direction', 'N/A')}°")
        print(f"   Regn (1h): {weather.get('rain', 0)} mm")
        print(f"   Luftfugtighed: {weather.get('humidity', 'N/A')}%")
        
        # Vurdering
        if route.get('weather_good') is not None:
            if route['weather_good']:
                print(f"\n   ✅ Vejret er godt til cykling!")
            else:
                print(f"\n   ⚠️  Vejret er ikke optimalt til cykling:")
                if weather.get('rain', 0) > 0.1:
                    print(f"      - Regn: {weather.get('rain', 0)} mm")
                if weather.get('wind_speed', 0) > 10:
                    print(f"      - Stærk vind: {weather.get('wind_speed', 0)} m/s")
                if weather.get('temperature', 0) < -5:
                    print(f"      - Koldt: {weather.get('temperature', 0)}°C")
    else:
        print("\n⚠️  Ingen vejrdata tilgængelig")
    
    # Gem rute
    print("\n💾 Gemmer rute...")
    files = finder.save_route(route, "aarhus_banegard_til_marselisborg")
    
    print(f"\n✅ Rute gemt!")
    print(f"   GPX fil: {files['gpx']}")
    print(f"   Kort: {files['map']}")


if __name__ == "__main__":
    main()


