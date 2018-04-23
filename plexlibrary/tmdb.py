# -*- coding: utf-8 -*-
import json
import shelve
import time
try:
    from cPickle import UnpicklingError
except ImportError:
    from pickle import UnpicklingError

import requests


class TMDb(object):
    api_key = None
    cache_file = None
    request_count = 0

    def __init__(self, api_key, cache_file=None):
        self.api_key = api_key
        if cache_file:
            self.cache_file = cache_file
        else:
            self.cache_file = 'tmdb_details.shelve'

    def get_imdb_id(self, tmdb_id, library_type='movie'):
        if library_type not in ('movie', 'tv'):
            raise Exception("Library type should be 'movie' or 'tv'")

        # Use cache
        cache = shelve.open(self.cache_file)
        if str(tmdb_id) in cache:
            try:
                cache_item = cache[str(tmdb_id)]
            except (EOFError, UnpicklingError):
                # Cache file error, clear
                cache.close()
                cache = shelve.open(self.cache_file, 'n')
            else:
                if (cache_item['cached'] + 3600 * 24) > int(time.time()):
                    cache.close()
                    return cache_item.get('imdb_id')

        # Wait 10 seconds for the TMDb rate limit
        if self.request_count >= 40:
            print(u"Waiting 10 seconds for the TMDb rate limit...")
            time.sleep(10)
            self.request_count = 0

        params = {
            'api_key': self.api_key,
        }

        if library_type == 'movie':
            url = "https://api.themoviedb.org/3/movie/{tmdb_id}".format(
                tmdb_id=tmdb_id)
        else:
            url = ("https://api.themoviedb.org/3/tv/{tmdb_id}/external_ids"
                   .format(tmdb_id=tmdb_id))
        r = requests.get(url, params=params)

        self.request_count += 1

        if r.status_code == 200:
            item = json.loads(r.text)
            item['cached'] = int(time.time())
            cache[str(tmdb_id)] = item
            cache.close()
            return item.get('imdb_id')
        else:
            return None

    def get_details(self, tmdb_id, library_type='movie'):
        if library_type not in ('movie', 'tv'):
            raise Exception("Library type should be 'movie' or 'tv'")

        # Use cache
        cache = shelve.open(self.cache_file)
        if str(tmdb_id) in cache:
            try:
                cache_item = cache[str(tmdb_id)]
            except (EOFError, UnpicklingError):
                # Cache file error, clear
                cache.close()
                cache = shelve.open(self.cache_file, 'n')
            else:
                if (cache_item['cached'] + 3600 * 24) > int(time.time()):
                    cache.close()
                    return cache_item

        # Wait 10 seconds for the TMDb rate limit
        if self.request_count >= 40:
            print(u"Waiting 10 seconds for the TMDb rate limit...")
            time.sleep(10)
            self.request_count = 0

        params = {
            'api_key': self.api_key,
        }

        if library_type == 'movie':
            params['append_to_response'] = 'release_dates'
            url = "https://api.themoviedb.org/3/movie/{tmdb_id}".format(
                    tmdb_id=tmdb_id)
        else:
            url = "https://api.themoviedb.org/3/tv/{tmdb_id}".format(
                    tmdb_id=tmdb_id)
        r = requests.get(url, params=params)

        self.request_count += 1

        if r.status_code == 200:
            item = json.loads(r.text)
            item['cached'] = int(time.time())
            cache[str(tmdb_id)] = item
            cache.close()
            return item
        else:
            return None
