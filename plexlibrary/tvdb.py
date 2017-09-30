# -*- coding: utf-8 -*-
import json

import requests


class TheTVDB(object):
    token = None
    def __init__(self, username, api_key, user_key):
        self.api_key = api_key
        self.user_key = user_key

    def get_imdb_id(self, tvdb_id):
        # TODO Cache
        if not self.token:
            self._refresh_token()

        url = "https://api.thetvdb.com/series/{tvdb_id}".format(tvdb_id=tvdb_id)
        headers = {
            'Authorization': 'Bearer {token}'.format(token=self.token)
        }
        r = requests.get(url, headers=headers)

        if r.status_code == 200:
            tv_show = r.json()
            return tv_show['data']['imdbId']
        else:
            return None

    def _refresh_token(self):
        data = {
            'apikey': config.TVDB_API_KEY,
            'userkey': config.TVDB_USER_KEY,
            'username': config.TVDB_USERNAME,
        }

        url = "https://api.thetvdb.com/login"
        r = requests.post(url, json=data)

        if r.status_code == 200:
            result = r.json()
            self.token = result['token']
        else:
            return None

