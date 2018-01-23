import utils
from stream import getCityFromTweet

def test_citiesList():
    cities = utils.getCities()
    assert ("Paris" in cities)

def test_cityDetect():
	tweets = [
		("The city of London.", "London"),
		("Give me Paris please", "Paris"),
		("Give me the city of Namur in Belgium please", "Namur")
	]

	for tweet, answer in tweets:
		assert(getCityFromTweet(tweet) == answer)