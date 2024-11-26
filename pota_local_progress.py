# POTA Local Parks Progress Script
# By Ian Renton, November 2024
# Queries the Parks on the Air API to find your closest parks, and prints the status of whether
# you have activated them.
# See the README.md file for more details.
# This is Public Domain software, see the LICENCE file


import click
from requests_cache import CachedSession
from datetime import timedelta
import great_circle_calculator.great_circle_calculator as gcc
import maidenhead as mh
import sys

@click.command()
@click.option('-n', 'num_parks', help='Number of parks to display', default=10)
@click.option('-c', 'callsign', help='Callsign to display', required=True)
@click.option('-lat', 'lat', help='Latitude of location')
@click.option('-lon', 'lon', help='Longitude of location')
@click.option('-grid', 'grid', help='Gridsquare of location')
@click.option('-unit', 'unit',
              type=click.Choice(['km', 'mi'], case_sensitive=False), help='Enter units in km or ft', default='km')
def main(num_parks, callsign, lat, lon, grid, unit):
    if lat or lon:
        lat = float(lat)
        lon = float(lon)
    else:
        lat, lon = mh.to_location(grid)
    if 'km' in unit:
        user_unit = 'kilometers'
    if 'mi' in unit:
        user_unit = 'miles'

    # Fetch list of parks within +-1 degree lat/lon of your location.
    session = CachedSession("pota-local-progress-cache", expire_after=timedelta(days=1))
    parks = session.get(
        "https://api.pota.app/park/grids/" + str(lat - 1.0) + "/" + str(lon - 1.0) + "/" + str(lat + 1.0) + "/" + str(
            lon + 1.0) + "/0").json()["features"]

    # For each park, calculate its distance and store it with the rest of the data
    home = (lon, lat)
    for park in parks:
        park_loc = (park["geometry"]["coordinates"][0], park["geometry"]["coordinates"][1])
        park["properties"]["distance_from_home"] = gcc.distance_between_points(home, park_loc, unit=user_unit,
                                                                            haversine=True)

    # Sort parks by distance from you, and limit to the number we are insterested in
    parks.sort(key=lambda x: x["properties"]["distance_from_home"])
    parks = parks[:num_parks]

    # Initially mark all parks as not activated
    for park in parks:
        park["properties"]["activated"] = False

    # Fetch a list of parks activated by the user, and mark them as activated. Note that this
    # is only "recent activity" and therefore probably an incomplete list, really we want the
    # full list, but it does not seem to be available publicly.
    activations = session.get("https://api.pota.app/profile/" + callsign).json()["recent_activity"]["activations"]
    for park in parks:
        for activation in activations:
            if park["properties"]["reference"] == activation["reference"]:
                park["properties"]["activated"] = True
                break

    # As a work-around for the incomplete data, we also try querying each park, to see if the
    # user appears in its list of activators. I'm not sure if this is really a complete list.
    for park in parks:
        activations = session.get(
            "https://api.pota.app/park/activations/" + park["properties"]["reference"] + "?count=all").json()
        for activation in activations:
            if callsign == activation["activeCallsign"]:
                park["properties"]["activated"] = True
                break

    # Write output
    print("The closest " + str(num_parks) + " parks to " + callsign + " QTH at " + str(lat) + ", " + str(lon) + " are:")
    print("  Status  | Distance | Reference | Name")
    print("----------|----------|-----------|----------------------------------------------")
    for park in parks:
        status_text_ansi = "\033[32mActivated\033[0m" if park["properties"]["activated"] else "\033[31m Pending \033[0m"
        limited_len_name = (park["properties"]["name"][:43] + '..') if len(park["properties"]["name"]) > 43 else \
            park["properties"]["name"]
        print(status_text_ansi + " | "
            + ("{:.1f}".format(park["properties"]["distance_from_home"]) + f" {unit}").rjust(8) + " | "
            + park["properties"]["reference"].center(9) + " | " + limited_len_name)

if __name__ == "__main__":
    main()