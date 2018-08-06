#!/usr/bin/python
import feedparser


#Set Variables to ensure we start fresh
min_temp = ''
max_temp = ''
current_temp = ''

#OpenweatherMap Settings
owm_api = '' #http://openweathermap.org/appid#get
owm_cityid = '' #Search for city ID here: http://openweathermap.org/help/city_list.txt. ID is the first column
owm_unit = 'metric' #metric or imperial

#Open Weather Map API URL
weatherURL = feedparser.parse ('http://api.openweathermap.org/data/2.5/weather?id=%s&appid=%s&mode=xml&units=%s' % (owm_cityid, owm_api, owm_unit))

#Get Yahoo Weather Code, min temp, max temp and weather text summary
min_temp = weatherURL.feed.temperature.get('min')
max_temp = weatherURL.feed.temperature.get('max')
current_temp = weatherURL.feed.temperature.get('value')
forecast_text = weatherURL.feed.weather.get('value')
