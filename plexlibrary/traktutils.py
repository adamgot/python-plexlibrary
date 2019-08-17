# -*- coding: utf-8 -*-
import datetime
import json

import requests
import trakt

from utils import add_years


class Trakt(object):
    def __init__(self, username, client_id='', client_secret='',
                 oauth_token='', oauth=False, config=None):
        self.config = config
        self.username = username
        self.client_id = client_id
        self.client_secret = client_secret
        self.oauth_token = oauth_token
        self.oauth = oauth
        if oauth:
            if not self.oauth_token:
                self.oauth_auth()
        else:
            trakt.core.pin_auth(username, client_id=client_id,
                                client_secret=client_secret)
        self.trakt = trakt
        self.trakt_core = trakt.core.Core()

    def oauth_auth(self):
        store = False
        self.oauth_token = trakt.core.oauth_auth(
            self.username, client_id=self.client_id,
            client_secret=self.client_secret, store=store)
        # Write to the file
        if self.config:
            self.config['trakt']['oauth_token'] = self.oauth_token
            self.config.save()
            print(u"Added new OAuth token to the config file under trakt:")
            print(u"    oauth_token: '{}'".format(self.oauth_token))

    def _handle_request(self, method, url, data=None):
        """Stolen from trakt.core to support optional OAUTH operations
        :todo: Fix trakt
        """
        headers = {'Content-Type': 'application/json',
                   'trakt-api-version': '2'}
        # self.logger.debug('%s: %s', method, url)
        headers['trakt-api-key'] = self.client_id
        if self.oauth:
            headers['Authorization'] = 'Bearer {0}'.format(self.oauth_token)
        # self.logger.debug('headers: %s', str(headers))
        # self.logger.debug('method, url :: %s, %s', method, url)
        if method == 'get':  # GETs need to pass data as params, not body
            response = requests.request(method, url, params=data,
                                        headers=headers)
        else:
            response = requests.request(method, url, data=json.dumps(data),
                                        headers=headers)
        # self.logger.debug('RESPONSE [%s] (%s): %s',
        #     method, url, str(response))
        if response.status_code in self.trakt_core.error_map:
            if response.status_code == \
                    trakt.core.errors.OAuthException.http_code:
                # OAuth token probably expired
                print(u"Trakt OAuth token invalid/expired")
                self.oauth_auth()
                return self._handle_request(method, url, data)
            raise self.trakt_core.error_map[response.status_code]()
        elif response.status_code == 204:  # HTTP no content
            return None
        json_data = json.loads(response.content.decode('UTF-8', 'ignore'))
        return json_data

    def add_movies(self, url, movie_list=None, movie_ids=None, max_age=0):
        if not movie_list:
            movie_list = []
        if not movie_ids:
            movie_ids = []
        max_date = add_years(max_age * -1)
        print(u"Retrieving the trakt list: {}".format(url))
        data = {}
        if max_age != 0:
            data['extended'] = 'full'
        movie_data = self._handle_request('get', url, data=data)
        for m in movie_data:
            if 'movie' not in m:
                m['movie'] = m
            # Skip already added movies
            if m['movie']['ids']['imdb'] in movie_ids:
                continue
            if not m['movie']['year']:  # TODO: Handle this better?
                continue
            # Skip old movies
            if max_age != 0 \
                    and (max_date > datetime.datetime.strptime(
                        m['movie']['released'], '%Y-%m-%d')):
                continue
            movie_list.append({
                'id': m['movie']['ids']['imdb'],
                'tmdb_id': m['movie']['ids'].get('tmdb', ''),
                'title': m['movie']['title'],
                'year': m['movie']['year'],
            })
            movie_ids.append(m['movie']['ids']['imdb'])
            if m['movie']['ids'].get('tmdb'):
                movie_ids.append('tmdb' + str(m['movie']['ids']['tmdb']))

        return movie_list, movie_ids

    def add_shows(self, url, show_list=None, show_ids=None, max_age=0):
        if not show_list:
            show_list = []
        if not show_ids:
            show_ids = []
        curyear = datetime.datetime.now().year
        print(u"Retrieving the trakt list: {}".format(url))
        data = {}
        if max_age != 0:
            data['extended'] = 'full'
        show_data = self._handle_request('get', url, data=data)
        for m in show_data:
            if 'show' not in m:
                m['show'] = m
            # Skip already added shows
            if m['show']['ids']['imdb'] in show_ids:
                continue
            if not m['show']['year']:
                continue
            # Skip old shows
            if max_age != 0 \
                    and (curyear - (max_age - 1)) > int(m['show']['year']):
                continue
            show_list.append({
                'id': m['show']['ids']['imdb'],
                'tmdb_id': m['show']['ids'].get('tmdb', ''),
                'tvdb_id': m['show']['ids'].get('tvdb', ''),
                'title': m['show']['title'],
                'year': m['show']['year'],
            })
            show_ids.append(m['show']['ids']['imdb'])
            if m['show']['ids'].get('tmdb'):
                show_ids.append('tmdb' + str(m['show']['ids']['tmdb']))
            if m['show']['ids'].get('tvdb'):
                show_ids.append('tvdb' + str(m['show']['ids']['tvdb']))

        return show_list, show_ids

    def add_items(self, item_type, url, item_list=None, item_ids=None,
                  max_age=0):
        if item_type == 'movie':
            return self.add_movies(url, movie_list=item_list,
                                   movie_ids=item_ids, max_age=max_age)
        elif item_type == 'tv':
            return self.add_shows(url, show_list=item_list,
                                  show_ids=item_ids, max_age=max_age)
