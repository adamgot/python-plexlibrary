# -*- coding: utf-8 -*-
import shelve

import requests

TMDB_REQUEST_COUNT = 0  # DO NOT CHANGE


def get_imdb_id(tmdb_id, library_type='movie'):
    global TMDB_REQUEST_COUNT

    if library_type not in ('movie', 'tv'):
        raise Exception("Library type should be 'movie' or 'tv'")

    # Use cache
    cache = shelve.open(config.TMDB_CACHE_FILE)
    if cache.has_key(str(tmdb_id)):
        item = cache[str(tmdb_id)]
        cache.close()
        return item.get('imdb_id')

    if not config.TMDB_API_KEY:
        cache.close()
        return None

    # Wait 10 seconds for the TMDb rate limit
    if TMDB_REQUEST_COUNT >= 40:
        print(u"Waiting 10 seconds for the TMDb rate limit...")
        time.sleep(10)
        TMDB_REQUEST_COUNT = 0

    params = {
        'api_key': config.TMDB_API_KEY,
    }

    if library_type == 'movie':
        url = "https://api.themoviedb.org/3/movie/{tmdb_id}".format(
            tmdb_id=tmdb_id)
    else:
        url = "https://api.themoviedb.org/3/tv/{tmdb_id}/external_ids".format(
            tmdb_id=tmdb_id)
    r = requests.get(url, params=params)

    TMDB_REQUEST_COUNT += 1

    if r.status_code == 200:
        item = json.loads(r.text)
        item['cached'] = int(time.time())
        cache[str(tmdb_id)] = item
        cache.close()
        return item.get('imdb_id')
    else:
        cache.close()
        return None


def get_details(tmdb_id, library_type='movie'):
    global TMDB_REQUEST_COUNT

    if library_type not in ('movie', 'tv'):
        raise Exception("Library type should be 'movie' or 'tv'")

    # Use cache
    cache = shelve.open(config.TMDB_CACHE_FILE)
    if cache.has_key(str(tmdb_id)) and \
            (cache[str(tmdb_id)]['cached'] + 3600 * 24) > int(time.time()):
        item = cache[str(tmdb_id)]
        cache.close()
        return item

    if not config.TMDB_API_KEY:
        cache.close()
        return None

    # Wait 10 seconds for the TMDb rate limit
    if TMDB_REQUEST_COUNT >= 40:
        print(u"Waiting 10 seconds for the TMDb rate limit...")
        time.sleep(10)
        TMDB_REQUEST_COUNT = 0

    params = {
        'api_key': config.TMDB_API_KEY,
    }

    if library_type == 'movie':
        params['append_to_response'] = 'release_dates'
        url = "https://api.themoviedb.org/3/movie/{tmdb_id}".format(
                tmdb_id=tmdb_id)
    else:
        url = "https://api.themoviedb.org/3/tv/{tmdb_id}".format(
                tmdb_id=tmdb_id)
    r = requests.get(url, params=params)

    TMDB_REQUEST_COUNT += 1

    if r.status_code == 200:
        item = json.loads(r.text)
        item['cached'] = int(time.time())
        cache[str(tmdb_id)] = item
        cache.close()
        return item
    else:
        cache.close()
        return None

