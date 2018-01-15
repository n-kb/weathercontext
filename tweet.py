from utils import makeGraph, sendTweet, CITIES
import os

for city in CITIES:
    makeGraph(city)

if os.environ["DEBUG"] == "False":
    sendTweet("Berlin")