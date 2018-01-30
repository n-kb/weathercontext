from utils import getTemp, sendTweet, CITIES
import os
import datetime as dt

def updateCities():

    # Gets the current time
    now = dt.datetime.utcnow()
    current_hour = now.hour

    for city in CITIES:
        # Makes the graph for each city if it's noon o'clock
        if current_hour + int(CITIES[city]["timezone"]) == 12:
            getTemp(CITIES[city]["name"], CITIES[city]["country"])
            
            if os.environ["DEBUG"] == "False" and city == "Berlin":
                sendTweet("Berlin")

    return "OK"


if __name__ == "__main__":
    updateCities()