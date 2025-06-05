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
from trakt import Trakt
from trakt.objects import Episode, Movie
from config import *
import dotenv
import time
from threading import Condition



from trakt import Trakt

from threading import Condition
import logging
import os

logging.basicConfig(level=logging.DEBUG)


class Application(object):
    def __init__(self):
        self.is_authenticating = Condition()

        self.authorization = None
        
        self.points = []
        self.posters = {}

        # Bind trakt events
        Trakt.on('oauth.token_refreshed', self.on_token_refreshed)

    def check_authentication(self):
        if os.path.isfile('auth.json'):
            try:
                with open('auth.json') as auth_file:
                    auth_data = json.load(auth_file)
                    TOKEN = auth_data['access_token']
                    REFRESH_TOKEN = auth_data['refresh_token']
                    expired = (time.time()-auth_data['created_at']) >=  auth_data['expires_in']
            except:
                expired = True
                pass

            if expired:
                print('Authentification expired, trying to re-authentificate...')
                return None

            return auth_data
        else:
            print('Authentication File not found!\n Trying first authentication ...')
            return None

    def authenticate(self):
        self.authorization = self.check_authentication()
        if self.authorization is not None:
            return True
        
        if not self.is_authenticating.acquire(blocking=False):
            print('Authentication has already been started')
            return False

        # Request new device code
        code = Trakt['oauth/device'].code()

        print('Enter the code "%s" at %s to authenticate your account' % (
            code.get('user_code'),
            code.get('verification_url')
        ))

        # Construct device authentication poller
        poller = Trakt['oauth/device'].poll(**code)\
            .on('aborted', self.on_aborted)\
            .on('authenticated', self.on_authenticated)\
            .on('expired', self.on_expired)\
            .on('poll', self.on_poll)

        # Start polling for authentication token
        poller.start(daemon=False)

        # Wait for authentication to complete
        return self.is_authenticating.wait()

    def run(self,start_Date):
       
        self.authenticate()
        
        if not self.authorization:
            print('ERROR: Authentication required')
            exit(1)
            
        connect(TRAKT_DATABASE)

        # Simulate expired token
        #self.authorization['expires_in'] = 0

        # Test authenticated calls
        #with Trakt.configuration.oauth.from_response(self.authorization):
        #    # Expired token, requests will return `None`
        #    print(Trakt['sync/collection'].movies())

        with Trakt.configuration.oauth.from_response(self.authorization, refresh=True):
            # Expired token will be refreshed automatically (as `refresh=True`)
            print(Trakt['sync/collection'].movies())

        with Trakt.configuration.oauth.from_response(self.authorization):
            # Current token is still valid
            print(Trakt['sync/collection'].movies())
            
        self.process_trakt_history(start_date)

    def on_aborted(self):
        """Device authentication aborted.

        Triggered when device authentication was aborted (either with `DeviceOAuthPoller.stop()`
        or via the "poll" event)
        """

        print('Authentication aborted')

        # Authentication aborted
        self.is_authenticating.acquire()
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

    def on_authenticated(self, authorization):
        """Device authenticated.

        :param authorization: Authentication token details
        :type authorization: dict
        """

        # Acquire condition
        self.is_authenticating.acquire()

        # Store authorization for future calls
        self.authorization = authorization

        print('Authentication successful - authorization: %r' % self.authorization)
        f = open('auth.json','w')
        json.dump(self.authorization, f)
        f.close()
        
        print(Trakt.client.configuration.oauth.owner)


        # Authentication complete
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

    def on_expired(self):
        """Device authentication expired."""

        print('Authentication expired')

        # Authentication expired
        self.is_authenticating.acquire()
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

    def on_poll(self, callback):
        """Device authentication poll.

        :param callback: Call with `True` to continue polling, or `False` to abort polling
        :type callback: func
        """

        # Continue polling
        callback(True)

    def on_token_refreshed(self, authorization):
        # OAuth token refreshed, store authorization for future calls
        self.authorization = authorization

        print('Token refreshed - authorization: %r' % self.authorization)



    def fetch_poster(self,type, tmdb_id):
        if tmdb_id == None:
            return None
        logging.info("Fetching poster for type=%s id=%s", type, tmdb_id)
        try:
            with requests_cache.enabled('tmdb'):
                response = requests.get(f'https://api.themoviedb.org/3/{type}/{tmdb_id}', 
                params={'api_key': TMDB_API_KEY})
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            logging.error("HTTP request failed: %s", err)
            return None

        data = response.json()
        if 'poster_path' in data and data['poster_path'] != None:
            return TMDB_IMAGE_BASE + 'w154' + data['poster_path']
        else:
            return None

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
    Trakt.base_url = 'https://api.trakt.tv'

    Trakt.configuration.defaults.client(
        id=os.environ.get('TRAKT_CLIENT_ID'),
        secret=os.environ.get('TRAKT_CLIENT_SECRET')
    )

    if len(sys.argv) > 1:
        xDate = sys.argv[1]
        start_date = datetime.strptime(xDate, '%Y-%m-%d').date()
    else:
        start_date = datetime(date.today().year, date.today().month, 1)

    app = Application()
    app.run(start_date)