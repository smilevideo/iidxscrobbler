# -*- coding: utf-8 -*-	

import sys, httplib, urllib, importio, latch, string, pymongo
from usermanager import getDatabase
from secrets import *

reload(sys)
sys.setdefaultencoding("utf-8")

songdata = None
playerdata = None
cookies = {'pw': None, 'ps': None}

#scrape data from import.io
def scrapeData(userid, network):
	client = clientGen()
	client.connect()
	queryLatch = latch.latch(1)

	global target_url, connector_guid, short_url

	#if the userid is 'refresh_music', this method will update the music library, otherwise it will check the user's recently played
	#stuff for scraping programmed sun
	cookie = cookies[network]
	if(network == 'ps'):
		short_url = "webui.programmedsun.com"
		if userid == "refresh_music":
			print "refreshing PS song list..."
			target_url = "http://webui.programmedsun.com/iidx/0/music"
			connector_guid = "e53e03d2-1468-4ebb-8fe9-2ef64de33db2"
		else:
			print "refreshing PS player %s's tracklist..." % userid
			target_url = "http://webui.programmedsun.com/iidx/0/players/%s/scores" % userid
			connector_guid = "9247219f-a36f-4e6b-85b0-1956eff5836d"
	#stuff for scraping programmed world
	elif(network == 'pw'):
		short_url = "programmedworld.net"
		if(userid == "refresh_music"):
			print "refreshing PW song list..."
			target_url = "https://programmedworld.net/iidx/22/music"
			connector_guid = "7d120ee9-000f-43f1-961a-17e4ff45771e"
		else:
			print "refreshing PW player %s's tracklist..." % userid
			target_url = "https://programmedworld.net/iidx/22/players/%s/scores" % userid
			connector_guid = "329e12e0-85ea-4961-83b6-a1156e25d46a"
	#callback to export the returned data
	def callback(query, message):
		global data
		if message["type"] == "DISCONNECT":
			print "Query in progress when library disconnected"
		if message["type"] == "MESSAGE":
			if "errorType" in message["data"]:
				#handle users with hidden accounts
				if "Not authorised" in message["data"]["error"]:
					print "This user has a hidden profile!"
					data = "ERROR"
				else:
					print "An error occured."
					print json.dumps(message, indent = 4)
					data = "ERROR"
			else:
				#handle non-existant users
				if message["data"]["results"] == [] and userid != 'refresh_music':
					print json.dumps(message, indent = 4)
					print "Non-existent user."
					data = "ERROR"
				else:
					data = (message["data"]["results"])
		
		if query.finished(): 
			queryLatch.countdown()

	#import.io's template queries sure are awesome
	client.query({
		"connectorGuids":[
			connector_guid
		],
		"input": {
			"webpage/url": target_url
		},
		"additionalInput": {
			connector_guid: {
				"cookies": [cookie]
			}
		}
	}, callback)

	queryLatch.await()
	client.disconnect()

	return data

# refreshes song list and converts to dictionary where key is songid
# and value is tuple (title, artist)
def refreshSongList(network):
	database = getDatabase()

	raw_data = scrapeData('refresh_music', network)

	for song in raw_data:
		songid = stripSongURL(song, network)
		title = song["song_info/_text"]
		#strip out stupid leggendaria suffix
		if "†LEGGENDARIA" in song["song_info/_text"]:
			title = song["song_info/_text"].replace("†LEGGENDARIA", "")

		database.musiclist.insert(
				{
					"songid": songid,
					"title": title,
					"artist": song["artist"]
				})


#strip song url to its numerical id
def stripSongURL(song, network):
	global songurl
	#for whatever reason the programmed world scraper leaves an
	#extra slash in the source url, will look into later
	if network == 'pw':
		songurl = song["song_info/_source"][15:]
	else:
		songurl = song["song_info/_source"][14:]
	return songurl[:songurl.index('/')]


#return song info from main data bank
def songLookup(songid):
	return getDatabase().musiclist.find_one({"songid": songid})

def generateCookies():
	#makes a small to import.io to just login and return a cookie without loading
	#anything else
	for network in ['ps']:
		client = clientGen()
		client.connect()
		queryLatch = latch.latch(1)
		global target_url, connector_guid, short_url, username, password
		
		if(network == 'ps'):
			print "getting PS cookie..."
			short_url = "webui.programmedsun.com"
			target_url = "http://webui.programmedsun.com/iidx/0/music"
			connector_guid = "e53e03d2-1468-4ebb-8fe9-2ef64de33db2"
			username = PS_USER
			password = PS_PWD
		elif(network == 'pw'):
			print "getting PW cookie..."
			short_url = "programmedworld.net"
			target_url = "https://programmedworld.net/iidx/22/music"
			connector_guid = "7d120ee9-000f-43f1-961a-17e4ff45771e"		
			username = PW_USER
			password = PW_PWD
		#callback to export the returned data
		def callback(query, message):
			if message["type"] == "DISCONNECT":
				print "Query in progress when library disconnected"
			if message["type"] == "MESSAGE":
				if "errorType" in message["data"]:
					print "Got an error!" 
					#handle users with hidden accounts
					print "An error occured."
					print json.dumps(message["data"], indent = 4)
					data = "ERROR"
				else:
					cookies[network] = message["data"]["cookies"][0]
			if query.finished(): 
				queryLatch.countdown()
		#import.io's template queries sure are awesome
		client.query({
			"connectorGuids":[
				connector_guid
			],
			"input": {
				"webpage/url": target_url
			},
			"loginOnly": 'true',
			"additionalInput": {
				connector_guid: {
					"domainCredentials":{
						short_url:{
							"username": username,
							"password": password
						}
					}
				}
			}
		}, callback)

		queryLatch.await()
		client.disconnect()
		print cookies

#makes this file double as a convenient way to refresh song lists from the server
#after wiping the database manually
if __name__ == '__main__':
	generateCookies()

	refreshSongList('pw')
	refreshSongList('ps')