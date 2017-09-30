# -*- coding: utf-8 -*-
import requests

TVDB_TOKEN = None


def get_imdb_id(tvdb_id):
    global TVDB_TOKEN
    # TODO Cache

    if not config.TVDB_API_KEY:
        return None

    if not TVDB_TOKEN:
        data = {
            "apikey": config.TVDB_API_KEY,
            "userkey": config.TVDB_USER_KEY,
            "username": config.TVDB_USERNAME,
        }

        url = "https://api.thetvdb.com/login"
        r = requests.post(url, json=data)

        if r.status_code == 200:
            result = r.json()
            TVDB_TOKEN = result['token']
        else:
            return None

    url = "https://api.thetvdb.com/series/{id}".format(id=tvdb_id)
    r = requests.get(url, headers={'Authorization': 'Bearer {token}'.format(token=TVDB_TOKEN)})

    if r.status_code == 200:
        tv_show = r.json()
        return tv_show['data']['imdbId']
    else:
        return None

