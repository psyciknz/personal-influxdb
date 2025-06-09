#!/usr/bin/python3
# Copyright 2022 Sam Steele
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests, requests_cache, sys, os, json
from datetime import datetime, date
from config import *
import dotenv
import time
from threading import Condition



from threading import Condition
import logging
import os

logging.basicConfig(level=logging.DEBUG)


class Application(object):
    def __init__(self):
        
        self.points = []
        self.posters = {}

        
    def run(self,json_file):
       
        connect(TRAKT_DATABASE)

        json_data = {}

        with open(json_file) as json_file:
            json_data = json.load(json_file)
            json_file.close()
            
        self.process_ryot_media('book',json_data)
        
    def process_ryot_media(self,type,json_data ):
        for item in json_data['media']:
            print(item)
            if item['lot'] == type:
                print("book")
                    
                    
    
        
    def process_trakt_history(self,start_date):
        with Trakt.configuration.oauth.from_response(self.authorization):
            traktHistory = Trakt['sync/history/'].get(pagination=True, per_page=100, start_at=start_date, extended='full')
            for item in traktHistory:
                logging.info("Item: %s (%s)" % (item, item.action))
                if (item.action == "watch" or item.action == "checkin" or item.action =="scrobble"):
                    if isinstance(item, Episode):
                        logging.info("Found episode: %s" % item.show.title) 
                        if not item.show.get_key('tmdb') in self.posters:
                            self.posters[item.show.get_key('tmdb')] = self.fetch_poster('tv', item.show.get_key('tmdb'))
                        if self.posters[item.show.get_key('tmdb')] == None:
                            html = None
                        else:
                            html = '<img src="' + self.posters[item.show.get_key('tmdb')] + '"/>'
                        self.points.append({
                            "measurement": "watch",
                            "time": item.watched_at.isoformat(),
                            "tags": {
                                "id": item.get_key('trakt'),
                                "show": item.show.title,
                                "show_id": item.show.get_key('trakt'),
                                "season": item.pk[0],
                                "episode": item.pk[1],
                                "type": "episode"
                            },
                            "fields": {
                                "title": item.title,
                                "tmdb_id": item.show.get_key('tmdb'),
                                "duration": item.show.runtime,
                                "poster": self.posters[item.show.get_key('tmdb')],
                                "poster_html": html,
                                "slug": item.show.get_key('slug'),
                                "url": f"https://trakt.tv/shows/{item.show.get_key('slug')}",
                                "episode_url": f"https://trakt.tv/shows/{item.show.get_key('slug')}/seasons/{item.pk[0]}/episodes/{item.pk[1]}"
                            }
                        })
                    elif isinstance(item, Movie):
                        logging.info("Found movie: %s" % item) 

                        if not item.get_key('tmdb') in self.posters:
                            self.posters[item.get_key('tmdb')] = self.fetch_poster('movie', item.get_key('tmdb'))
                        if self.posters[item.get_key('tmdb')] == None:
                            html = None
                        else:
                            html = f'<img src="{self.posters[item.get_key("tmdb")]}"/>'
                        self.points.append({
                            "measurement": "watch",
                            "time": item.watched_at.isoformat(),
                            "tags": {
                                "id": item.get_key('trakt'),
                                "type": "movie"
                            },
                            "fields": {
                                "title": item.title,
                                "tmdb_id": item.get_key('tmdb'),
                                "duration": item.runtime,
                                "poster": self.posters[item.get_key('tmdb')],
                                "poster_html": html,
                                "slug": item.get_key('slug'),
                                "url": f"https://trakt.tv/movie/{item.get_key('slug')}"
                            }
                        })
                    else:
                        logging.info("Couldn't determine type from %s" % item)
                    if len(self.points) >= 500:
                        write_points(self.points)
                        self.points = []

        write_points(self.points)
    #def process_trakt_history(self,start_date):





if __name__ == '__main__':
    # Configure
    
    if len(sys.argv) > 1:
        json_file= sys.argv[1]
        if not os.path.exists(json_file):
            print(f"File {json_file} does not exist")
            sys.exit(4)
            
    
    app = Application()
    app.run(json_file)