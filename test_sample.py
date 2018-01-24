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

def test_cityDistance():
	london = [-0.118092,51.509865]
	paris = [2.352222,48.856614]

	assert (utils.getDistance(paris[0], paris[1], london[0], london[1]) == 340)