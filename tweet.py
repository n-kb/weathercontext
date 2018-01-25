from utils import makeGraph, sendTweet, CITIES
import os
import datetime as dt

def updateCities():

    # Gets the current time
    now = dt.datetime.utcnow()
    current_hour = now.hour

    for city in CITIES:
        # Makes the graph for each city if it's noon o'clock
        if current_hour + int(CITIES[city]["timezone"]) == 12:
            new_record = makeGraph(CITIES[city]["name"], CITIES[city]["country"])
        
            if os.environ["DEBUG"] == "False" and city == "Berlin":
                sendTweet("Berlin", new_record=new_record)

    return "OK"


if __name__ == "__main__":
    updateCities()