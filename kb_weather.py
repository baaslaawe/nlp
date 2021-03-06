#!/usr/bin/env python
# -*- coding: utf-8 -*- 

#
# Copyright 2014, 2015, 2016 Guenter Bartsch
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

#
# fetch weather forecast data from OpenWeatherMap, generate and store triples
#

import os
import sys
import locale
import ConfigParser
from os.path import expanduser
from optparse import OptionParser
import traceback
import codecs

# from rdflib import Graph, Literal, BNode, Namespace, RDF, URIRef
# from rdflib.namespace import DC, FOAF

from urllib2 import HTTPError
from datetime import datetime, timedelta
import pytz
import json
import urllib2
from tzlocal import get_localzone
import astral

from kb import HALKB

import model

WEATHER_BASE_FN = 'data/src/kb/weather_base.n3'
KELVIN          = 273.15

def get_timestamps ():

    # timestamps we're interested in:

    dt = datetime.now(get_localzone()).replace(tzinfo=pytz.utc)

    dts = [
              # today
              (dt + timedelta(days=0)).replace (hour= 9, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=0)).replace (hour=15, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=0)).replace (hour=21, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=1)).replace (hour= 3, minute=0, second=0, microsecond=0),

              # tomorrow
              (dt + timedelta(days=1)).replace (hour= 9, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=1)).replace (hour=15, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=1)).replace (hour=21, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=2)).replace (hour= 3, minute=0, second=0, microsecond=0),

              # day after tomorrow
              (dt + timedelta(days=2)).replace (hour= 9, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=2)).replace (hour=15, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=2)).replace (hour=21, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=3)).replace (hour= 3, minute=0, second=0, microsecond=0),  

              # + 3 days
              (dt + timedelta(days=3)).replace (hour= 9, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=3)).replace (hour=15, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=3)).replace (hour=21, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=4)).replace (hour= 3, minute=0, second=0, microsecond=0),

              # + 4 days
              (dt + timedelta(days=4)).replace (hour= 9, minute=0, second=0, microsecond=0),  
              (dt + timedelta(days=4)).replace (hour=15, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=4)).replace (hour=21, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=5)).replace (hour= 3, minute=0, second=0, microsecond=0),
        ]

    return dts

#
# load config, set up global variables
#

api_key    = model.config.get("weather", "api_key")

#
# init terminal
#

reload(sys)
sys.setdefaultencoding('utf-8')
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

#
# knowledge base
#

kb = HALKB()

#
# fetch city ids, timezones
#

locations = {}

print "fetching city ids, timezones from kb..."

query = """
        SELECT DISTINCT ?location ?cityid ?timezone ?label ?lat ?long
               WHERE {
                  ?location weather:cityid ?cityid .
                  ?location weather:timezone ?timezone .
                  ?location rdfs:label ?label .
                  ?location geo:lat ?lat .
                  ?location geo:long ?long .
                  FILTER(LANGMATCHES(LANG(?label), "en")) .
        }
        """

try:
    results = kb.query(query)

    # print repr(results)

    for result in results["results"]["bindings"]:
        # print repr(result)
        #         print(result["label"]["value"])

        location = result[u'location'][u'value']
        city_id  = result[u'cityid'][u'value']
        timezone = result[u'timezone'][u'value']
        label    = result[u'label'][u'value']
        geo_lat  = result[u'lat'][u'value']
        geo_long = result[u'long'][u'value']

        if not location in locations:
            locations[location] = {}
            locations[location]['city_id']  = int(city_id)
            locations[location]['timezone'] = timezone
            locations[location]['label']    = label
            locations[location]['long']     = float(geo_long)
            locations[location]['lat']      = float(geo_lat)

            print "   %s %s %d %f %f" % (label, timezone, int(city_id), float(geo_long), float(geo_lat))

except HTTPError:
    traceback.print_exc()

# print repr(locations)

#
# fetch weather data from OpenWeatherMap
#

weather_data = {} # city_id -> dt -> forecast_dict

print "fetching weather data from OpenWeatherMap..."

for location in locations:

    city_id = locations[location]['city_id']

    # fetch json forecast data

    url = 'http://api.openweathermap.org/data/2.5/forecast?id=%s&APPID=%s' % (city_id, api_key)

    data = json.load(urllib2.urlopen(url))

    # print repr(data['list'])

    weather_data[city_id] = {}

    for fc in data['list']:

        dt_cur = datetime.strptime (fc['dt_txt'], '%Y-%m-%d %H:%M:%S')
        dt_cur = dt_cur.replace(tzinfo=pytz.utc)

        w_cur = { 'dt'            : dt_cur, 
                  'city_id'       : city_id,
                  'temp_min'      : fc['main']['temp_min']-KELVIN,
                  'temp_max'      : fc['main']['temp_max']-KELVIN,
                  'code'          : fc['weather'][0]['id'],
                  'precipitation' : float(fc['rain']['3h']) if 'rain' in fc and '3h' in fc['rain'] else 0.0,
                  'icon'          : fc['weather'][0]['icon'],
                  'description'   : fc['weather'][0]['description'],
                  'clouds'        : float(fc['clouds']['all'])
                }

        weather_data[city_id][dt_cur] = w_cur

        print "   got weather forecast for %s on %s city_id=%s" % (location, dt_cur, city_id)

# print repr(weather_data)

#
# create triples for timespans we're potentially interested in
#

#          ( label       from day, from hour, to day, to hour ) 
tspans = [ 
           ( 'morning'  ,       0,         5,      0,      11 ),
           ( 'noon'     ,       0,        11,      0,      17 ),
           ( 'evening'  ,       0,        17,      0,      23 ),
           ( 'night'    ,       0,        23,      1,       5 ),
           ( 'wholeDay' ,       0,         5,      1,       5 ),

           ( 'morning'  ,       1,         5,      1,      11 ),
           ( 'noon'     ,       1,        11,      1,      17 ),
           ( 'evening'  ,       1,        17,      1,      23 ),
           ( 'night'    ,       1,        23,      2,       5 ),
           ( 'wholeDay' ,       1,         5,      2,       5 ),

           ( 'morning'  ,       2,         5,      2,      11 ),
           ( 'noon'     ,       2,        11,      2,      17 ),
           ( 'evening'  ,       2,        17,      2,      23 ),
           ( 'night'    ,       2,        23,      3,       5 ),
           ( 'wholeDay' ,       2,         5,      3,       5 ),

           ( 'morning'  ,       3,         5,      3,      11 ),
           ( 'noon'     ,       3,        11,      3,      17 ),
           ( 'evening'  ,       3,        17,      3,      23 ),
           ( 'night'    ,       3,        23,      4,       5 ),
           ( 'wholeDay' ,       3,         5,      4,       5 ),

           ( 'twoDays'  ,       0,         5,      2,       5 ),
           ( 'twoDays'  ,       1,         5,      3,       5 ),
           ( 'twoDays'  ,       2,         5,      4,       5 ),

           ( 'threeDays',       0,         5,      3,       5 ),
           ( 'threeDays',       1,         5,      4,       5 ),
           ( 'threeDays',       2,         5,      5,       5 ),
         ]

def mangle_uri(label):
    return ''.join(map(lambda c: c if c.isalnum() else '_', label))

for location in locations:

    print "working on %s" % location

    city_id   = locations[location]['city_id']
    timezone  = locations[location]['timezone']
    loc_label = mangle_uri(locations[location]['label'])
    geo_lat   = locations[location]['lat']
    geo_long  = locations[location]['long']
    
    if not city_id in weather_data:
        continue

    tz = pytz.timezone(timezone)

    ref_dt = datetime.now(tz).replace( hour        = 0,
                                       minute      = 0,
                                       second      = 0,
                                       microsecond = 0)

    # print location, ref_dt

    #
    # sunrise / sunset
    #

    l = astral.Location()
    l.name      = 'name'
    l.region    = 'region'
    l.latitude  = geo_lat
    l.longitude = geo_long
    l.timezone  = timezone
    l.elevation = 0

    for day_offset in range(7):
        cur_date = (ref_dt + timedelta(days=day_offset)).date()

        sun = l.sun(date=cur_date, local=True)

        sun_uri = 'weather:sun_%s_%s' % (loc_label, cur_date.strftime('%Y%m%d'))

        query = """
                INSERT {
                   GRAPH <http://hal.zamia.org>
                   { 
                       %s weather:location <%s> .
                       %s weather:date "%s" .
                       %s weather:dawn "%s"   .
                       %s weather:sunrise "%s"   .
                       %s weather:noon "%s"   .
                       %s weather:sunset "%s"   .
                       %s weather:dusk "%s"   .
                   }
                }
                """ % ( sun_uri, location, \
                        sun_uri, cur_date.isoformat(), \
                        sun_uri, sun['dawn'].isoformat(), \
                        sun_uri, sun['sunrise'].isoformat(), \
                        sun_uri, sun['noon'].isoformat(), \
                        sun_uri, sun['sunset'].isoformat(), \
                        sun_uri, sun['dusk'].isoformat())

        # print query

        result = kb.sparql(query)

        if result.status_code == 200:
            print "astral  ", location, cur_date.isoformat(), result.status_code
        else:
            print "astral  ", location, cur_date.isoformat(), result.status_code, result.text

    #
    # weather forecast
    #

    for tspan in tspans:

        label, from_day, from_hour, to_day, to_hour = tspan

        from_dt = ref_dt + timedelta(hours=from_day*24 + from_hour)
        to_dt   = ref_dt + timedelta(hours=  to_day*24 +   to_hour)

        fc_uri = 'weather:fc_%s_%s_%s' % (loc_label, from_dt.strftime('%Y%m%d'), label)

        # print fc_uri, label, from_dt, to_dt

        icon          = '01d.png'
        temp_min      = 200.0
        temp_max      = -200.0
        precipitation = 0.0
        clouds        = 0.0
        num           = 0

        for fc_dt in weather_data[city_id]:
            if fc_dt < from_dt or fc_dt > to_dt:
                continue
            # print "   ", fc_dt

            fc = weather_data[city_id][fc_dt]
            if fc['temp_min'] < temp_min:
                temp_min = fc['temp_min']
            if fc['temp_max'] > temp_max:
                temp_max = fc['temp_max']

            if fc['icon'] > icon:
                icon = fc['icon']

            precipitation += fc['precipitation']
            clouds        += fc['clouds']
            num += 1

        if num == 0:
            print "   *** ERROR: no data found for %s - %s in %s." % (from_dt, to_dt, location)
            continue

        clouds = clouds / float(num)

        # print "   TEMP RANGE:",temp_min, temp_max

        query = """
                WITH <http://hal.zamia.org>
                DELETE { %s ?p ?v }
                WHERE { %s ?p ?v }
                """ % (fc_uri, fc_uri)

        result = kb.sparql(query)

        if result.status_code == 200:
            print "cleared %s:" % fc_uri, result.status_code
        else:
            print "cleared %s:" % fc_uri, result.status_code, result.text

        query = """
                INSERT {
                   GRAPH <http://hal.zamia.org>
                   { 
                       %s weather:location <%s> .
                       %s weather:temp_min %f   .
                       %s weather:temp_max %f   .
                       %s weather:precipitation %f .
                       %s weather:clouds %f .
                       %s weather:icon "%s" .
                       %s weather:dt_start "%s" .
                       %s weather:dt_end "%s" .
                   }
                }
                """ % ( fc_uri, location, fc_uri, temp_min, fc_uri, temp_max, \
                        fc_uri, precipitation, fc_uri, clouds, fc_uri, icon,  \
                        fc_uri, from_dt.isoformat(), fc_uri, to_dt.isoformat())

        # print query

        result = kb.sparql(query)

        if result.status_code == 200:
            print "stored  %s: " % fc_uri, result.status_code
        else:
            print "stored  %s: " % fc_uri, result.status_code, result.text


sys.exit(0)


#
# create graph
#

WEATHER = Namespace('http://hal.zamia.org/weather/')

DBR = Namespace('http://dbpedia.org/resource/')
DBO = Namespace('http://dbpedia.org/ontology/')

g = Graph()

g.parse(WEATHER_BASE_FN, format='n3')

# dbr:Reykjavík         weather:cityid 3413829 .
# dbr:Washington,_D.C.  weather:cityid 4140963 .
# dbr:Fairbanks,_Alaska weather:cityid 5861897 .
# g.set( (URIRef('http://dbpedia.org/resource/Reykjavík'),         WEATHER.cityid, Literal(3413829)) )
# g.set( (URIRef('http://dbpedia.org/resource/Washington,_D.C.'),  WEATHER.cityid, Literal(4140963)) )
# g.set( (URIRef('http://dbpedia.org/resource/Fairbanks,_Alaska'), WEATHER.cityid, Literal(5861897)) )

print( g.serialize(format='n3') )




sys.exit(0)



# wev = WEATHER.fcStuttgart2016116Morning
# 
# g.set( (wev, WEATHER.tempMin, Literal(10.0)) )
# g.set( (wev, WEATHER.tempMax, Literal(15.0)) )
# g.set( (wev, DBO.location, DBR.Stuttgart) )

# store city ids

# stuttgart, freudental, tallinn, san francisco, los angeles, new york,  london,   paris, Reykjavik IS, Washington D.C., Fairbanks, Oberwiesenthal, Arnstorf, Hamburg
# 2825297,      2924888,  588409,       5391959,     5368361,  5128581, 2643743, 2988507,      3413829,         4140963,   5861897,        2882332,  2854179, 2911298
g.set( (DBR.Stuttgart,  WEATHER.cityid, Literal(2825297)) )
g.set( (DBR.Freudental, WEATHER.cityid, Literal(2924888)) )

# Bind a few prefix, namespace pairs for more readable output

g.bind("weather", WEATHER)
g.bind("dbr", DBR)
g.bind("dbo", DBO)

print( g.serialize(format='n3') )

with codecs.open(WEATHER_BASE_FN, 'w', 'utf8') as n3f:
    n3f.write(g.serialize(format='n3'))

sys.exit(0)

#############################################################################################
#
# FIXME: remove old code below
#


WEATHERFN = 'data/dst/weather-dynamic.pl'
TEMP_OFFSET = 3.0

class Forecast(object):

    def __init__(self, dt, temp_min, temp_max, code, precipitation, icon, description, clouds):

        self.dt            = dt
        self.temp_min      = temp_min
        self.temp_max      = temp_max
        self.code          = code
        self.precipitation = precipitation
        self.icon          = icon
        self.description   = description
        self.clouds        = clouds

    def __str__(self):
        return "Forecast (dt=%s, temp_min=%d, temp_max=%d, code=%s, icon=%s, description=%s, clouds=%d)" % (self.dt, 
                                                                                    self.temp_min, 
                                                                                    self.temp_max, 
                                                                                    self.code,
                                                                                    self.icon, 
                                                                                    self.description,
                                                                                    self.clouds)


def get_timestamps ():

    # timestamps we're interested in:

    dt = datetime.now(get_localzone()).replace(tzinfo=pytz.utc)

    dts = [
              # today 0
              (dt + timedelta(days=0)).replace (hour= 9, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=0)).replace (hour=15, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=0)).replace (hour=21, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=1)).replace (hour= 3, minute=0, second=0, microsecond=0),

              # tomorrow 4
              (dt + timedelta(days=1)).replace (hour= 9, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=1)).replace (hour=15, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=1)).replace (hour=21, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=2)).replace (hour= 3, minute=0, second=0, microsecond=0),

              # day after tomorrow 8
              (dt + timedelta(days=2)).replace (hour= 9, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=2)).replace (hour=15, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=2)).replace (hour=21, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=3)).replace (hour= 3, minute=0, second=0, microsecond=0),

              # + 3 days 12
              (dt + timedelta(days=3)).replace (hour= 9, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=3)).replace (hour=15, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=3)).replace (hour=21, minute=0, second=0, microsecond=0),
              (dt + timedelta(days=4)).replace (hour= 3, minute=0, second=0, microsecond=0),

              # + 4 days 16
              # (dt + timedelta(days=4)).replace (hour= 9, minute=0, second=0, microsecond=0),
              # (dt + timedelta(days=4)).replace (hour=15, minute=0, second=0, microsecond=0),
              # (dt + timedelta(days=4)).replace (hour=21, minute=0, second=0, microsecond=0),
              # (dt + timedelta(days=5)).replace (hour= 3, minute=0, second=0, microsecond=0),
        ]

    return dts

#
# load config, set up global variables
#

db_server  = model.config.get("weather", "dbserver")
db_name    = model.config.get("weather", "dbname")
db_user    = model.config.get("weather", "dbuser")
db_pass    = model.config.get("weather", "dbpass")
city_pred  = model.config.get("weather", "city_pred")

#
# init terminal
#

reload(sys)
sys.setdefaultencoding('utf-8')
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

#
# connect to DB
#

conn_string = "host='%s' dbname='%s' user='%s' password='%s'" % (db_server, db_name, db_user, db_pass)

conn = psycopg2.connect(conn_string)

cur = conn.cursor()

#
# main
#

# timestamps we're interested in:
dts = get_timestamps()

forecasts = []

for dt in dts:

    # print dt

    # print "SELECT temp_min, temp_max, code, precipitation, icon, description, clouds FROM weather_forecast WHERE dt=%s" % dt

    cur.execute ("SELECT temp_min, temp_max, code, precipitation, icon, description, clouds FROM weather_forecast WHERE dt=%s", (dt,))

    row = cur.fetchone()

    # print row
    
    fc = Forecast (dt            = dt, 
                   temp_min      = float(row[0]),
                   temp_max      = float(row[1]),
                   code          = row[2],
                   precipitation = float(row[3]),
                   icon          = row[4],
                   description   = row[5],
                   clouds        = float(row[6]))

    # print "FC   %s" % (str(fc))
    forecasts.append(fc)


#
# dump prolog code
#

dt_today = datetime.now(get_localzone()).replace(tzinfo=pytz.utc)

def make_dt (days, hour):
    global dt_today

    return (dt_today + timedelta(days=days)).replace (hour= hour, minute=0, second=0, microsecond=0)



forecast_slices = {
    'today'                    : (forecasts[ 0: 3], make_dt(0,  0), make_dt(1,  0)),
    'todayMorning'             : (forecasts[ 0: 1], make_dt(0,  0), make_dt(0, 12)),
    'todayAfternoon'           : (forecasts[ 1: 2], make_dt(0, 12), make_dt(0, 18)),
    'todayEvening'             : (forecasts[ 2: 3], make_dt(0, 18), make_dt(1,  0)),

    'tomorrow'                 : (forecasts[ 4: 7], make_dt(1,  0), make_dt(2,  0)),
    'tomorrowMorning'          : (forecasts[ 4: 5], make_dt(1,  0), make_dt(1, 12)),
    'tomorrowAfternoon'        : (forecasts[ 5: 6], make_dt(1, 12), make_dt(1, 18)),
    'tomorrowEvening'          : (forecasts[ 6: 7], make_dt(1, 18), make_dt(2,  0)),

    'dayAfterTomorrow'         : (forecasts[ 8:11], make_dt(2,  0), make_dt(3,  0)),
    'dayAfterTomorrowMorning'  : (forecasts[ 8: 9], make_dt(2,  0), make_dt(2, 12)),
    'dayAfterTomorrowAfternoon': (forecasts[ 9:10], make_dt(2, 12), make_dt(2, 18)),
    'dayAfterTomorrowEvening'  : (forecasts[10:11], make_dt(2, 18), make_dt(3,  0)),
    
    'nextThreeDays'            : (forecasts[ 4:15], make_dt(1,  0), make_dt(4,  0)),
    }

def myCap(s):
    return s[0].capitalize() + s[1:]

iconDesc = {
    "01" : "weatherCondClearSky",
    "02" : "weatherCondFewClouds",
    "03" : "weatherCondScatteredClouds",
    "04" : "weatherCondBrokenClouds",
    "09" : "weatherCondShowerRain",
    "10" : "weatherCondRain",
    "11" : "weatherCondThunderstorm",
    "13" : "weatherCondSnow",
    "50" : "weatherCondMist",
}

with open(WEATHERFN, 'w') as weatherf:

    weatherf.write ("% prolog\n")
    weatherf.write ("\n")
    weatherf.write ("%! module weather-dynamic\n")
    weatherf.write ("\n")

    for span in forecast_slices:

        event_id = 'eWeather'+myCap(city_pred)+myCap(span)

        icon          = '01d.png'
        temp_min      = 200.0
        temp_max      = -200.0
        precipitation = 0.0
        clouds        = 0.0
        num           = 0

        for fc in forecast_slices[span][0]:

            if fc.icon > icon:
                icon = fc.icon
            if fc.temp_min < temp_min:
                temp_min = fc.temp_min
            if fc.temp_max > temp_max:
                temp_max = fc.temp_max
            precipitation += fc.precipitation
            clouds        += fc.clouds
            num += 1

        clouds = clouds / float(num)

        dt_start = forecast_slices[span][1]
        dt_end   = forecast_slices[span][2]

        weatherf.write ("%\n")
        weatherf.write ("%% %s\n" % span)
        weatherf.write ("%\n")

        # weatherf.write ("startTime(%s,X) :- date_time_stamp(date(%d,%d,%d,%d,%d,%d,'local'),X)." % (span, dt_start.year, dt_start.month,
        #                                                                                   dt_start.day, dt_start.hour, 
        #                                                                                   dt_start.minute,
        #                                                                                   dt_start.second))
        # weatherf.write ("endTime(%s,X) :- date_time_stamp(date(%d,%d,%d,%d,%d,%d,'local'),X)." % (span, dt_end.year, dt_end.month,
        #                                                                                   dt_end.day, dt_end.hour, 
        #                                                                                   dt_end.minute,
        #                                                                                   dt_end.second))
        weatherf.write ("time(%s,%s).\n" % (event_id, span))
        weatherf.write ("place(%s,%s).\n" % (event_id, city_pred))
        weatherf.write ("weatherDesc(%s,%s).\n" % (event_id, iconDesc[icon[0:2]]))
        weatherf.write ("tempMin(%s,%s).\n" % (event_id, temp_min + TEMP_OFFSET))
        weatherf.write ("tempMax(%s,%s).\n" % (event_id, temp_max + TEMP_OFFSET))
        weatherf.write ("precipitation(%s,%s).\n" % (event_id, precipitation))
        weatherf.write ("cloudiness(%s,%s).\n" % (event_id, clouds))
        weatherf.write ("\n")

print "%s written." % WEATHERFN
print

