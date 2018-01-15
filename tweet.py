from utils import makeGraph, sendTweet, makeTweet, CITIES
import os

for city in CITIES:
    title, plt = makeGraph("Berlin")

if os.environ["DEBUG"] == "True":
    plt.savefig("temp/graph.png", format='png')
else:
    makeTweet("Berlin")