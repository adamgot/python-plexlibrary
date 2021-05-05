# -*- coding: utf-8 -*-
import json
import shelve
import time
try:
    from cPickle import UnpicklingError
except ImportError:
    from pickle import UnpicklingError

import requests

import logs


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
            logs.info(u"Waiting 10 seconds for the TMDb rate limit...")
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
            except:
                # Unknown cache file error, clear
                logs.error(u"Error in loading cache: {}".format(e))
                cache.close()
                cache = shelve.open(self.cache_file, 'n')
            else:
                if (cache_item['cached'] + 3600 * 24) > int(time.time()):
                    cache.close()
                    return cache_item

        # Wait 10 seconds for the TMDb rate limit
        if self.request_count >= 40:
            logs.info(u"Waiting 10 seconds for the TMDb rate limit...")
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

    def get_tmdb_from_imdb(self, imdb_id, library_type):
        if library_type not in ('movie', 'tv'):
            raise Exception("Library type should be 'movie' or 'tv'")

        # Use cache
        cache = shelve.open(self.cache_file)
        if str(imdb_id) in cache:
            try:
                cache_item = cache[str(imdb_id)]
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
            logs.info(u"Waiting 10 seconds for the TMDb rate limit...")
            time.sleep(10)
            self.request_count = 0

        params = {
            'api_key': self.api_key,
            'external_source': 'imdb_id'
        }

        url = "https://api.themoviedb.org/3/find/{imdb_id}".format(
            imdb_id=imdb_id)

        r = requests.get(url, params=params)

        self.request_count += 1

        media_result = None

        if r.status_code == 200:
            item = json.loads(r.text)

            if library_type == 'movie':
                if item and item.get('movie_results'):
                    media_result = item.get('movie_results')[0]
            else:
                if item and item.get('tv_results'):
                    media_result = item.get('tv_results')[0]

            if media_result:
                media_result['cached'] = int(time.time())
                cache[str(imdb_id)] = media_result

        cache.close()
        return media_result
