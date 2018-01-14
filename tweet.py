from utils import makeGraph, sendTweet

title, plt = makeGraph("Berlin")

if os.environ["DEBUG"] == "True":
    plt.savefig("temp/graph.png", format='png')
else:
    sendTweet(title, plt)