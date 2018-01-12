import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import ConnectionPatch
import matplotlib.font_manager as font_manager
import csv
import datetime as dt
from scipy.interpolate import interp1d
from colour import Color
import requests, json, io, boto3
from twitter import *
import matplotlib

matplotlib.use('Agg')

def getTemp():
    city = "Berlin"
    url = "http://api.openweathermap.org/data/2.5/weather?q=%s&APPID=%s" % (city, OWMKEY)
    r = requests.get(url)
    json_data = json.loads(r.text)
    # returns temperature in Celsius
    return json_data["main"]["temp"] - 272.15

def saveToS3(plt):
    img_data = io.BytesIO()
    plt.savefig(img_data, format='png')
    img_data.seek(0)
    filename = dt.date.today().strftime("%Y-%B-%d") + "-Berlin.png"
    client = boto3.client(
        's3',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY
    )
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(BUCKET_NAME)
    bucket.put_object(Body=img_data, ContentType='image/png', Key=filename, ACL='public-read')
    return "https://s3-eu-west-1.amazonaws.com/weathercontext/" + filename

def sendTweet(status_text, plt):
    imagedata = io.BytesIO()
    plt.savefig(imagedata, format='png')
    imagedata.seek(0)
    
    t = Twitter(
            auth=OAuth(ACCESS_TOKEN, ACCESS_SECRET, TWITTER_KEY, TWITTER_SECRET))

    t_upload = Twitter(domain='upload.twitter.com',
            auth=OAuth(ACCESS_TOKEN, ACCESS_SECRET, TWITTER_KEY, TWITTER_SECRET))
    
    id_img = t_upload.media.upload(media=imagedata.read())["media_id_string"]
   
    t.statuses.update(status=status_text, media_ids=id_img)


pd.options.mode.chained_assignment = None

df = pd.read_csv('cities_meteo.csv')

colors = {"lowkey_blue": "#737D99", "dark_blue": "#335CCC", "cringing_blue": "#59DDFF", "lowkey_red":"#FFBB99", "strong_red": "#CC5033"}

current_temp = getTemp()

today = dt.date.today()

fig, ax = plt.subplots(1, 1, figsize=(12, 6))

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

    
subtitle = "Temperatures from 1979 to 2017 are shown below. The redder the color, the more recent the year."
if (diff_from_avg < -2):
    todays_text = "Today at noon, the temperature\nwas %d°C, lower than the\n1979-2000 average of %.2f°C."
    title = "%d°C today in Berlin, it's cold!"
elif (diff_from_avg < 2):
    todays_text = "Today at noon, the temperature\nwas %d°C, close to the\n1979-2000 average of %.2f°C."
    title = "%d°C today in Berlin, about average %s." % (current_temp, hot_or_cold)
elif (diff_from_avg < 5):
    todays_text = "Today at noon, the temperature\nwas %d°C, above the\n1979-2000 average of %.2f°C."
    title = "%d°C today in Berlin, pretty warm." % current_temp
else:
    todays_text = "Today at noon, the temperature\nwas %d°C, way above the\n1979-2000 average of %.2f°C."
    title = "%d°C today in Berlin, way too %s." % (current_temp, hot_or_warm)

# If new record
if (current_temp > max_temp):
    todays_text = "Today's record of %d° \nis much higher \nthan the 1979-2000 \naverage of %.2f°C."
    title = "%d°C today in Berlin, new record!" % current_temp
    
else:
    # Annotation for max value
    annotation_text = "On %s \nthe temperature reached %d°C."
    plt.annotate(annotation_text % (max_year.strftime("%B %d, %Y,"), max_temp), 
                 xy=(yday, max_temp), 
                 xytext=(yday+.7, max_temp + 3),
                 horizontalalignment='left', 
                 verticalalignment='top',
                 arrowprops=dict(arrowstyle="->",
                                connectionstyle="arc3,rad=-0.3"
                                )
                )

# Annotation for today's value
plt.annotate(todays_text % (current_temp, today_average), 
             xy=(yday, current_temp), 
             xytext=(yday+.7, current_temp - 2),
             horizontalalignment='left', 
             verticalalignment='top',
             arrowprops=dict(arrowstyle="->",
                            connectionstyle="arc3,rad=-0.3"
                            )
            )
# Focuses on today
ax.set_xlim([yday - 10,yday + 5])

font_color = "#676767"
serif_font = 'Bitstream Vera Serif'
sans_font = 'Liberation Sans'     
title_font = {'fontname':serif_font
             ,'size': 21
             ,'color': font_color}
subtitle_font = {'fontname':serif_font
                ,'size': 12
                ,'color': font_color}
label_font = {'fontname':sans_font
             ,'color': font_color
             ,'size': 10}

annotate_font = {'fontname':sans_font
             ,'color': font_color
             ,'size': 7}

smaller_font = {'fontname':sans_font
                ,'color': font_color
                , 'size': 7
                , 'weight': 'bold'}

## Adds title
plt.figtext(.05,.9,title, **title_font)
plt.figtext(.05, .83, subtitle, **subtitle_font)

## Adds source
plt.figtext(.05, .03, "Data source: ECMWF", **smaller_font)

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
## Reduces size of plot to allow for subtitle text
plt.subplots_adjust(top=0.75, bottom=0.08)

# img_url = saveToS3(plt)
sendTweet(title, plt)