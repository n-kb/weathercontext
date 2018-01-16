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
import requests, io, json, boto3, os, csv
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
                "country":row[4]
            }
    return cities

CITIES = getCities()

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

    class CityGraph(BaseModel):
        image_url = CharField()
        city = CharField()
        title = CharField()
        date = DateField()

        class Meta:
            primary_key = CompositeKey('city', 'date')


    db.connect()
    db.create_tables([CityGraph], safe=True)

    return CityGraph

def getTemp(city, country):

    url = "http://api.openweathermap.org/data/2.5/weather?q=%s,%s&APPID=%s" % (city, country, os.environ["OWMKEY"])
    r = requests.get(url)
    json_data = json.loads(r.text)
    # returns temperature in Celsius
    return json_data["main"]["temp"] - 272.15

def saveToS3(plt, city):
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)
    filename = "%s-%s.png" % (dt.date.today().strftime("%Y-%m-%d"), city)

    if os.environ["DEBUG"] == "True":
        plt.savefig("temp/%s" % filename, format='png')

    s3_session = boto3.Session(
        aws_access_key_id=os.environ["ACCESS_KEY"],
        aws_secret_access_key=os.environ["SECRET_KEY"],
        region_name='us-east-1'
    )
    s3 = s3_session.resource('s3')
    bucket = s3.Bucket(os.environ["BUCKET_NAME"])
    bucket.put_object(Body=img_data, ContentType='image/png', Key=filename, ACL='public-read')
    return "https://s3-eu-west-1.amazonaws.com/weathercontext/" + filename

def storeResult(image_url, city, title, today):

    CityGraph = dbInit()

    try:
        CityGraph.create(
            image_url = image_url,
            city = city,
            title = title,
            date = today
        )
        print ("\033[92mInserted data for %s.\033[0m" % city)

    except IntegrityError:
        # Could not insert, probably bc it already exists
        print ("\033[93mCould not insert data for %s.\033[0m" % city)
        pass

def sendTweet(city, username = None, reply_to = None):

    CityGraph = dbInit()
    no_graph = 0
    yesterday = None
    
    # Fetches image from DB
    # The time is adapted to the timezone, Heroku works in UTC
    time_offset = int(CITIES[city]["timezone"])
    today = dt.datetime.now() + dt.timedelta(hours=time_offset)
    citygraphs = CityGraph.select().where(CityGraph.date == today.strftime("%Y-%m-%d")).where(CityGraph.city == city)

    # If there is a graph ready for the day
    if (citygraphs.count() == 1):
        citygraph = citygraphs[0]

    # In case there is no graph for today's data, maybe there is one for yesterday
    else:
        yesterday = today - dt.timedelta(days=1)
        citygraphs = CityGraph.select().where(CityGraph.date == yesterday.strftime("%Y-%m-%d")).where(CityGraph.city == city)
        if (citygraphs.count() == 1):
            citygraph = citygraphs[0]
        else:
            no_graph = 1


    if no_graph == 1:
        status_text = "@%s 🐕 I have data for %s but the first contextual report will be created at noon local time. Check back later!" % (username, city)
    else:
        if reply_to == None:
            status_text = citygraph.title
        elif yesterday is not None: 
            status_text = "@%s Here's the context data for %s you wanted! It's yesterday's data because I only refresh my graphs at noon local time. 🐕🐕" % (username, city)
        else:
            status_text = "@%s Here's the context data for %s you wanted! 🐕🐕" % (username, city)

        r = requests.get(citygraph.image_url, stream=True)
        r.raw.decode_content = True
        imagedata = r.raw.read()
    
    auth = OAuth(os.environ["ACCESS_TOKEN"], os.environ["ACCESS_SECRET"], os.environ["TWITTER_KEY"], os.environ["TWITTER_SECRET"])

    # Authenticate to twitter
    t = Twitter(auth=auth)

    t_upload = Twitter(domain='upload.twitter.com', auth=auth)
    
    # Sends image to twitter
    id_img = t_upload.media.upload(media=imagedata)["media_id_string"]
   
    # Tweets
    t.statuses.update(status=status_text, media_ids=id_img, in_reply_to_status_id=reply_to)

def makeGraph(city, country):
    # Prevents panda from producing a warning
    pd.options.mode.chained_assignment = None

    df = pd.read_csv('data/%s.csv' % city.lower())

    current_temp = getTemp(city, country)

    today = dt.date.today()

    # Converts date col to datetime
    df["Date"] = pd.to_datetime(df["Date"], format='%Y%m%d', errors='ignore')

    # Converts Kelvin to Celsius
    df["Value at MetPoint"] = df["Value at MetPoint"] - 272.15

    # Computes today's day number
    yday = today.toordinal() - dt.date(today.year, 1, 1).toordinal() + 1

    # Average for today 1979 - 2000
    df_today = df.loc[(df['Date'].dt.month == today.month) & (df['Date'].dt.day == today.day) & (df['Date'].dt.year <= 2000)]
    today_average = df_today["Value at MetPoint"].mean()

    # Get the max values
    df_today = df.loc[(df['Date'].dt.month == today.month) & (df['Date'].dt.day == today.day)]
    max_temp = df_today["Value at MetPoint"].max()
    max_id = df_today["Value at MetPoint"].idxmax()
    max_year = df_today.loc[max_id]["Date"]

    abs_max = -100
    abs_min = 100


    colors = {  "lowkey_blue": "#737D99", 
                "dark_blue": "#335CCC", 
                "cringing_blue": "#59DDFF", 
                "lowkey_red":"#FFBB99", 
                "strong_red": "#CC5033"}

    font_color = "#676767"
    serif_font = 'Ranga'
    sans_fontfile = 'fonts/LiberationSans-Regular.ttf'     
    serif_fontfile = 'fonts/VeraSerif.ttf'     
    title_font = {'fontproperties': font_manager.FontProperties(fname=serif_fontfile, size=21)
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

    fig, ax = plt.subplots(1, 1, figsize=(12, 6))

    # A color range for years
    color_ramp = list(Color("yellow").range_to(Color(colors["strong_red"]),2018-1979))

    # Plots curve for all years
    for year in range(1979, 2018):
        
        # Current day for year=year
        current_day = dt.datetime(year, today.month, today.day, 0, 0)
        
        # Creates a df from Jan 1 to today for given year
        df_year = df.loc[(df['Date'] >= str(year) + '-01-01') & (df['Date'] <= current_day)]
        
        # Remove February 29
        if year % 4 == 0:
            df_year = df_year.loc[((df_year['Date'] != str(year) + '-02-29'))]
        
        # Gets abs max and mins
        if df_year["Value at MetPoint"].max() > abs_max:
            abs_max = df_year["Value at MetPoint"].max()
        if df_year["Value at MetPoint"].min() < abs_min:
            abs_min = df_year["Value at MetPoint"].min()

        # Create a new column with day number
        num_days = df_year['Date'].count()
        df_year["day_num"] = np.arange(1,num_days + 1)
        
        # Plotting instructions
        lw = .3
        alpha = .5
        color = color_ramp[year-1979].rgb
        
        # Plots daily values
        ax.plot(yday, df.loc[(df['Date'] == current_day), "Value at MetPoint"], marker='o', color = color, alpha = alpha)
        
        # Makes a spline for past values
        xnew = np.linspace(yday - 11,yday, num=15*5, endpoint=True)
        f2 = interp1d(df_year["day_num"], df_year["Value at MetPoint"], kind='cubic')
        ax.plot(xnew, f2(xnew), color=color, lw=lw)

    # Plots today's value
    ax.plot(yday, current_temp, marker='o', color = colors["strong_red"])

    # Generate the texts
    diff_from_avg = current_temp - today_average

    hot_or_cold = "cold"
    hot_or_warm = "warm"
    if current_temp > 15:
        hot_or_cold = "warm"
    if current_temp > 25:
        hot_or_warm = "hot"

        
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
        
    else:
        # Annotation for max value
        annotation_text = "On %s \nthe temperature reached %d°C."
        plt.annotate(annotation_text % (max_year.strftime("%B %d, %Y,"), max_temp), 
                     xy=(yday, max_temp), 
                     xytext=(yday+.7, max_temp + 1),
                     horizontalalignment='left', 
                     verticalalignment='top',
                     **label_font_strong,
                     arrowprops=dict(arrowstyle="->",
                                    connectionstyle="arc3,rad=-0.3"
                                    )
                    )

    # Annotation for today's value
    plt.annotate(todays_text % (current_temp, today_average, today.strftime("%d %B")), 
                 xy=(yday, current_temp), 
                 xytext=(yday+.7, current_temp - 2),
                 horizontalalignment='left', 
                 verticalalignment='top',
                 **label_font_strong,
                 arrowprops=dict(arrowstyle="->",
                                connectionstyle="arc3,rad=-0.3"
                                )
                )

    # Annotation for the warmest and coldest years

    plt.annotate("Each line represents the temperature for a year.\nThis is 2016, warmest year on record.", 
                 xy=(yday - 9, df.loc[(df["Date"] == "2016-" + (today - dt.timedelta(days=9)).strftime("%m-%d"))]["Value at MetPoint"]), 
                 xytext=(yday - 8, abs_max+2),
                 horizontalalignment='left', 
                 verticalalignment='top',
                 **label_font,
                 arrowprops=dict(arrowstyle="->",
                                connectionstyle="arc3,rad=-0.3",
                                ec=font_color
                                )
                )

    plt.annotate("And this is 1979.\nYellow lines are for older years,\nred ones for more recent ones.", 
                 xy=(yday - 3, df.loc[(df["Date"] == "1979-" + (today - dt.timedelta(days=3)).strftime("%m-%d"))]["Value at MetPoint"]), 
                 xytext=(yday - 8, abs_min + 1),
                 horizontalalignment='left', 
                 verticalalignment='top',
                 **label_font,
                 arrowprops=dict(arrowstyle="->",
                                connectionstyle="arc3,rad=-0.3",
                                ec=font_color
                                )
                )

    # Focuses on today
    ax.set_xlim([yday - 10,yday + 5])

    # Forces spaces on top of chart
    ax.set_ylim([abs_min - 5, abs_max + 4])

    # Set x axis ticks
    times = pd.date_range(today - dt.timedelta(days=10), periods=15, freq='1d')
    xfmt = mdates.DateFormatter('%-d %B')
    ax.xaxis.set_major_formatter(xfmt)

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

    image_url = saveToS3(plt, city)

    storeResult(image_url, city, title, today)

    plt.close()