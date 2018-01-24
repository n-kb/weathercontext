import utils
import datetime as dt
from stream import getCityFromTweet

def test_citiesList():
    cities = utils.getCities()
    assert ("Paris" in cities)

def test_cityDetect():
	tweets = [
		("The city of London.", "London"),
		("Give me Paris please", "Paris")
	]

	for tweet, answer in tweets:
		assert(getCityFromTweet(tweet) == answer)

