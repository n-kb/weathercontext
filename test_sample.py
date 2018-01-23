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

def test_storeNewCity():
	
	CityGraph, CityRequest = utils.dbInit()

	city = "Munich"
	user = "tester"
	utils.storeRequest(city, user)

	test_city = CityRequest.select().where(CityRequest.city == city).where(CityRequest.user == user)

	assert(test_city.count() == 1)

	test_city = CityRequest.select().where(CityRequest.city == city).where(CityRequest.user == user).get()

	assert(test_city.delete_instance() == 1)