import matplotlib as mpl
mpl.use('Agg') # Needed as Heroku doesn't have the tk package installed

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import ConnectionPatch
import matplotlib.font_manager as font_manager
import matplotlib.ticker as mticker    
import datetime as dt
from scipy.interpolate import interp1d
from colour import Color
import MySQLdb
import requests, io, json, boto3, os, csv, math
import urllib.parse as urlparse
import peewee
from peewee import *
import matplotlib.dates as mdates
from twitter import *

if 'CLEARDB_DATABASE_URL' not in os.environ:
    from playhouse.sqlite_ext import SqliteExtDatabase

def getCities():
    cities = {}
    with open("data/cities.csv") as csv_file:
        reader = csv.reader(csv_file)
        # jumps headers
        next(reader)
        for row in reader:
            cities[row[0]] = {
                "name":row[0],
                "timezone":row[3],
                "country":row[4],
                "lat": float(row[2]),
                "lng": float(row[1])
            }
    return cities

CITIES = getCities()

def getGif():
    
    # Gets image from Giphy
    token = os.environ["GIPHY"]
    
    url = "https://api.giphy.com/v1/gifs/random?api_key=%s&tag=woot&rating=g" % token
    
    r = requests.get(url)
    json_data = json.loads(r.text)

    gif_url = json_data["data"]["image_url"]

    # Sends the image to Twitter
    r = requests.get(gif_url, stream=True)
    r.raw.decode_content = True
    imagedata = r.raw.read()

    auth = OAuth(os.environ["ACCESS_TOKEN"], os.environ["ACCESS_SECRET"], os.environ["TWITTER_KEY"], os.environ["TWITTER_SECRET"])

    # Authenticate to twitter
    t_upload = Twitter(domain='upload.twitter.com', auth=auth)
    
    # Sends image to twitter
    id_img = t_upload.media.upload(media=imagedata)["media_id_string"]

    return id_img

def dbInit():
    if 'CLEARDB_DATABASE_URL' in os.environ:
        PROD = True
        url = urlparse.urlparse(os.environ['CLEARDB_DATABASE_URL'])
        db = peewee.MySQLDatabase(url.path[1:], host=url.hostname, user=url.username, passwd=url.password)
    else:
        db = SqliteExtDatabase('weather.db')

    class BaseModel(Model):
        class Meta:
            database = db

    class CityTemp(BaseModel):
        city = CharField()
        temp = FloatField()
        date = DateField()

        class Meta:
            primary_key = CompositeKey('city', 'date')


    db.connect()
    db.create_tables([CityTemp], safe=True)

    return CityTemp

def geoloc (s):
    url = "http://nominatim.openstreetmap.org/search/?format=json&q=%s&limit=1" % s
    r = requests.get(url)
    json_data = json.loads(r.text)
    lng = json_data[0]["lon"]
    lat = json_data[0]["lat"]
    return (float(lng), float(lat))

def findClosest(city):
    lng, lat = geoloc(city)

    min_dist = 9999999

    for city_destination in CITIES:
        dist = getDistance(lng, lat, CITIES[city_destination]["lng"], CITIES[city_destination]["lat"])
        if dist < min_dist:
            min_dist = dist
            closest_city = CITIES[city_destination]["name"]

    return closest_city, min_dist


def getDistance(lon1, lat1, lon2, lat2):
    radius = 6371 # km

    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = radius * c
    
    return math.floor(d/10) * 10

def getTemp(city, country):

    # Exception for New York
    if city == "New York City":
        city = "New York"

    url = "http://api.openweathermap.org/data/2.5/weather?q=%s,%s&APPID=%s" % (city, country, os.environ["OWMKEY"])
    r = requests.get(url)
    json_data = json.loads(r.text)
    temp = json_data["main"]["temp"] - 272.15

    # Gets the local time of the city
    time_offset = int(CITIES[city]["timezone"])
    today = dt.datetime.now() + dt.timedelta(hours=time_offset)

    # Stores the temperature
    CityTemp = dbInit()

    try:
        CityTemp.create(
            city = city,
            date = today.strftime("%Y-%m-%d"),
            temp = temp
        )
        print ("\033[92mInserted data for %s.\033[0m" % city)

    except IntegrityError:
        # Could not insert, probably bc it already exists
        print ("\033[93mCould not insert data for %s.\033[0m" % city)
        pass

    # returns temperature in Celsius
    return temp

def sendTweet(city, username = None, reply_to = None):

    CityTemp = dbInit()
    no_graph = 0
    yesterday = None
    country = CITIES[city]["country"]
    
    # Fetches temp from DB
    # The time is adapted to the timezone, Heroku works in UTC
    time_offset = int(CITIES[city]["timezone"])
    today = dt.datetime.now() + dt.timedelta(hours=time_offset)
    citytemps = CityTemp.select().where(CityTemp.date == today.strftime("%Y-%m-%d")).where(CityTemp.city == city)

    # If there is a graph ready for the day
    if (citytemps.count() == 1):
        date_to_graph = today
        citytemp = citytemps[0].temp

    # In case there is no graph for today's data, maybe there is one for yesterday
    else:
        yesterday = today - dt.timedelta(days=1)
        date_to_graph = yesterday
        citytemps = CityTemp.select().where(CityTemp.date == yesterday.strftime("%Y-%m-%d")).where(CityTemp.city == city)
        if (citytemps.count() == 1):
            citytemp = citytemps[0].temp
        else:
            no_graph = 1

    if no_graph == 1:
        status_text = "@%s 🐕 I have data for %s but the first contextual report will be created at noon local time. Check back later!" % (username, city)
        imagedata = None
    else:
        imagedata, title, new_record = makeGraph(city, country, date=date_to_graph, current_temp=citytemp)
        if username == None:
            status_text = title
        elif yesterday is not None: 
            status_text = "@%s Here's the context data for %s you wanted! It's yesterday's data because I only refresh my graphs at noon local time. 🐕🐕" % (username, city)
        else:
            status_text = "@%s Here's the context data for %s you wanted! 🐕🐕" % (username, city)
  
    auth = OAuth(os.environ["ACCESS_TOKEN"], os.environ["ACCESS_SECRET"], os.environ["TWITTER_KEY"], os.environ["TWITTER_SECRET"])

    # Authenticate to twitter
    t = Twitter(auth=auth)

    # List of image ids
    img_ids = []

    if imagedata is not None:
        t_upload = Twitter(domain='upload.twitter.com', auth=auth)

        # Sends image to twitter
        img_ids.append(t_upload.media.upload(media=imagedata)["media_id_string"])

        if new_record == True:
            img_ids.append(getGif())
   
    img_ids = ",".join(img_ids)
    
    # Tweets
    if os.environ["DEBUG"] == "False":
        t.statuses.update(status=status_text, media_ids=img_ids, in_reply_to_status_id=reply_to)
    else:
        return status_text, img_ids

def makeGraph(city, country, date=None, current_temp=None):
    # Prevents panda from producing a warning
    pd.options.mode.chained_assignment = None

    fig, ax = plt.subplots(1, 1, figsize=(12, 6))

    df = pd.read_csv('data/%s.csv' % city.lower())

    if date == None:
        today = dt.date.today()
    else:
        today = date

    # If no current temperature is passed, fetches it
    if current_temp == None:
        CityTemp = dbInit()

        # Fetches temperature from DB
        citytemps = CityTemp.select().where(CityTemp.date == today.strftime("%Y-%m-%d")).where(CityTemp.city == city)
        if (citytemps.count() == 1):
            citytemp = citytemps[0]
            current_temp = citytemp.temp
        else:
            # No temperature found
            return False

    new_record = False

    # Converts date col to datetime
    df["Date"] = pd.to_datetime(df["Date"], format='%Y%m%d', errors='ignore')

    # Converts Kelvin to Celsius
    df["Value at MetPoint"] = df["Value at MetPoint"] - 272.15

    # Average for today 1979 - 2000
    df_today = df.loc[(df['Date'].dt.month == today.month) & (df['Date'].dt.day == today.day) & (df['Date'].dt.year <= 2000)]
    today_average = df_today["Value at MetPoint"].mean()

    # Get the max values
    df_today = df.loc[(df['Date'].dt.month == today.month) & (df['Date'].dt.day == today.day)]
    max_temp = df_today["Value at MetPoint"].max()
    min_temp = df_today["Value at MetPoint"].min()
    max_id = df_today["Value at MetPoint"].idxmax()
    max_year = df_today.loc[max_id]["Date"]

    # A color range for years
    # Temperatures are multiplied by 100 because the color scale works with integer, x100 allows for more granularity
    colors = {"lowkey_blue": "#737D99", "dark_blue": "#335CCC", "cringing_blue": "#59DDFF", "lowkey_red":"#FFBB99", "strong_red": "#CC5033"}
    color_ramp = list(Color("yellow").range_to(Color(colors["strong_red"]),int(max_temp*100)-int(min_temp*100)))
    x = range(1979, 2018)
    x_avg = range(1979 - 2, 2018 + 4)
    y =  df_today["Value at MetPoint"]
    avg = np.full((2018 + 4 - 1979 + 2), today_average)

    # Plots the average
    ax.plot(x_avg, avg, lw=.5, color="black", alpha=.4, linestyle='--')

    # Plots the vertical lines unders each dot
    for index, row in df_today.iterrows():
        temp = row["Value at MetPoint"]
        year = row['Date'].year
        color = color_ramp[int(temp*100-max_temp*100)].rgb
        if temp == max_temp:
            color = colors["strong_red"]
        ax.plot((year, year), (temp,today_average),  marker=None, color=color, alpha=.7)
        ax.plot(year, temp, color=color, marker="o")

    # Plots today's value
    ax.scatter(2018, current_temp, marker='o', color = colors["strong_red"])

    # Fits the x axis
    ax.set_xlim([1979 - 2, 2018 + 15])


    colors = {  "lowkey_blue": "#737D99", 
                "dark_blue": "#335CCC", 
                "cringing_blue": "#59DDFF", 
                "lowkey_red":"#FFBB99", 
                "strong_red": "#CC5033"}

    font_color = "#676767"
    sans_fontfile = 'fonts/LiberationSans-Regular.ttf'     
    serif_fontfile = 'fonts/VeraSerif.ttf'     
    title_font = {'fontproperties': font_manager.FontProperties(fname=serif_fontfile, size=21)
                  ,'color': font_color
                 }
    subtitle_font = {'fontproperties': font_manager.FontProperties(fname=serif_fontfile, size=12)
                  ,'color': font_color
                 }
    label_font = {'fontproperties': font_manager.FontProperties(fname=sans_fontfile, size=10)
                 ,'color': font_color
                 }

    label_font_strong = {'fontproperties': font_manager.FontProperties(fname=sans_fontfile, size=10)
                 ,'color': 'black'
                 }

    smaller_font = {'fontproperties': font_manager.FontProperties(fname=sans_fontfile, size=7)
                    ,'color': font_color
                    , 'weight': 'bold'}

    
    # Generate the texts
    diff_from_avg = current_temp - today_average

    hot_or_cold = "cold"
    hot_or_warm = "warm"
    if current_temp > 15:
        hot_or_cold = "warm"
    if current_temp > 25:
        hot_or_warm = "hot"

    subtitle = "Temperatures on %s in %s, 1979 to 2017. Colors show the distance to the 1979-2000 average temperature." % (today.strftime("%d %B"), city)
    if (diff_from_avg < -2):
        todays_text = "Today at noon, the temperature\nwas %d°C, lower than the\n1979-2000 average of %.2f°C\nfor a %s."
        title = "It's %d°C today in %s, pretty cold for a %s!"  % (current_temp, city, today.strftime("%d %B"))
    elif (diff_from_avg <= 2):
        todays_text = "Today at noon, the temperature\nwas %d°C, close to the\n1979-2000 average of %.2f°C\nfor a %s."
        title = "It's %d°C today in %s, about average %s for a %s." % (current_temp, city, hot_or_cold, today.strftime("%d %B"))
    elif (diff_from_avg <= 5):
        todays_text = "Today at noon, the temperature\nwas %d°C, above the\n1979-2000 average of %.2f°C\nfor a %s."
        title = "It's %d°C today in %s, pretty warm for a %s." % (current_temp, city, today.strftime("%d %B"))
    else:
        todays_text = "Today at noon, the temperature\nwas %d°C, way above the\n1979-2000 average of %.2f°C\nfor a %s."
        title = "It's %d°C today in %s, way too %s for a %s." % (current_temp, city, hot_or_warm, today.strftime("%d %B"))

    # If new record
    if (current_temp > max_temp):
        todays_text = "Today's record of %d° \nis much higher \nthan the 1979-2000 \naverage of %.2f°C\nfor a %s."
        title = "It's %d°C today in %s, new record for a %s!" % (current_temp, city, today.strftime("%d %B"))
        new_record = True
        
    # Annotation for today's value
    plt.annotate(todays_text % (current_temp, today_average, today.strftime("%d %B")), 
                 xy=(2018, current_temp), 
                 xytext=(2022, current_temp - 2),
                 horizontalalignment='left', 
                 verticalalignment='top',
                 **label_font_strong,
                 arrowprops=dict(arrowstyle="->",
                                connectionstyle="arc3,rad=-0.3"
                                )
                )

    # Set units for yaxis
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%d°C'))

    # Sets labels fonts for axes
    for label in ax.get_xticklabels():
        label.set_fontproperties(font_manager.FontProperties(fname=sans_fontfile))
        label.set_fontsize(9) 
    for label in ax.get_yticklabels():
        label.set_fontproperties(font_manager.FontProperties(fname=sans_fontfile))
        label.set_fontsize(9) 

    ## Adds title
    plt.figtext(.05,.9,title, **title_font)
    plt.figtext(.05, .83, subtitle, **subtitle_font)

    ## Adds source
    plt.figtext(.05, .03, "Data source: ECMWF, openweathermap", **smaller_font)

    ## Adds a horizontal line under the title
    con = ConnectionPatch(xyA=(.05,.88), xyB=(.95,.88), coordsA="figure fraction", coordsB="figure fraction", 
                          axesA=None, axesB=None, color=font_color, lw=.1)
    ax.add_artist(con)

    # Removes top and right axes
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    ## Sets axes color
    ax.spines['bottom'].set_color(font_color)
    ax.spines['left'].set_color(font_color)
    ax.tick_params(axis='x', colors=font_color)
    ax.tick_params(axis='y', colors=font_color)
    ax.yaxis.label.set_color(font_color)
    ax.xaxis.label.set_color(font_color)

    fig.tight_layout()

    ## Reduces size of plot to allow for text
    plt.subplots_adjust(top=0.75, bottom=0.10)

    # Saves image to disk locally
    if os.environ["DEBUG"] == "local":
        filename = city + today.strftime("%Y-%m-%d")
        plt.savefig("temp/%s" % filename, format='png')

    # Saves images to string
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)

    plt.close()

    return img_data.read(), title, new_record