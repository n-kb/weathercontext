import utils, tweet
import datetime as dt
from stream import getCityFromTweet

def test_citiesList():
    cities = utils.getCities()
    assert ("Paris" in cities)

def test_cityDetect():
	tweets = [
		("The city of London.", "London"),
		("Give me Paris please", "Paris"),
		("is Buenos Aires available?", "Buenos Aires")
	]

	for tweet, answer in tweets:
		assert(getCityFromTweet(tweet) == answer)

def test_cityDistance():
	london = [-0.118092,51.509865]
	paris = [2.352222,48.856614]

	assert (utils.getDistance(paris[0], paris[1], london[0], london[1]) == 340)

def test_findClosest():
	assert (utils.findClosest("Cologne") == ("Bonn", 20))

def test_geoloc():
	assert (utils.geoloc("Cologne") == (6.959974, 50.938361))

def test_gif():
	media_id = utils.getGif()
	print (media_id)
	assert (type(int(media_id)) == int)

def test_cityLoop():
	assert(tweet.updateCities() == "OK")

def test_sendTweet():
	tweet_text, media_ids = utils.sendTweet("London")
	assert(media_ids[0] == "[")
	assert(type(tweet_text) == str)