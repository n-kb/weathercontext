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

def test_getTemp():
	temp = utils.getTemp("Berlin", "DE")
	assert(type(temp) == float)

def test_makeGraph():
	img_data, title, new_record = utils.makeGraph("Berlin", "DE")
	assert(type(img_data) == bytes)
	img_data, title, new_record = utils.makeGraph("Berlin", "DE", date=dt.datetime.now(), current_temp=20)
	assert(new_record == True)
	img_data, title, new_record = utils.makeGraph("Berlin", "DE", date=dt.datetime.now(), current_temp=-10)
	assert(new_record == False)

def test_makeStats():
	img_data = utils.makeStats("Berlin")
	assert(type(img_data) == bytes)

def test_blankGraph():
	fig, ax = utils.blankGraph()
	print (fig.__class__)
	assert(fig.__class__.__name__ == 'Figure')

def test_sendTweet():
	status_text, img_ids = utils.sendTweet("Berlin")
	assert(type(status_text) == str)
	status_text, img_ids = utils.sendTweet("Bonn", username = "test_user", reply_to = "0000000")
	assert(type(status_text) == str)