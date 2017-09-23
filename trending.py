#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Automated Trending Plex library script

Usage:
    # FIXME

Requirements:
    requests
    plexapi
    trakt

Disclaimer:
    Use at your own risk! I am not responsible for damages to your Plex server or libraries.

Author:
    /u/haeri

Credit:
    Originally based on https://gist.github.com/JonnyWong16/f5b9af386ea58e19bf18c09f2681df23
    by /u/SwiftPanda16
"""

import sys
import os
import json
import subprocess
import time
import datetime
import shelve

import requests
from plexapi.server import PlexServer
import trakt

# Config
# Plex server details
PLEX_URL = 'http://localhost:32400'
# See https://support.plex.tv/hc/en-us/articles/204059436-Finding-an-authentication-token-X-Plex-Token
PLEX_TOKEN = 'QnBqu4ShyssKtevLpsxe'
PLEX_HOME_DIR = "/usr/lib/plexmediaserver"
PLEX_MEDIA_SCANNER_PATH = '/usr/lib/plexmediaserver/Plex Media Scanner'

# Trakt API details
# Required
# Create a Trakt account, then create an API app here:
# https://trakt.tv/oauth/applications/new
TRAKT_USERNAME = 'adamgo'
TRAKT_CLIENT_ID = '2235fccf434eb71fece00771ac46c32bb4d199ae8c075f9550de2fec89f2be1f'
TRAKT_CLIENT_SECRET = 'b6bf4d62ba16fb88ed127c303d48fded6a7f19255b1deb8f92f90cc8682de3f8'
# Experiment with the limits in the URLs below to get a different balance.
TRAKT_LIST_URLS = [
    'https://api.trakt.tv/movies/trending?limit=2',
    'https://api.trakt.tv/movies/watched/weekly?limit=80',
    'https://api.trakt.tv/movies/watched/monthly?limit=150',
    'https://api.trakt.tv/movies/watched/yearly?limit=500',
]

LIBRARY_TYPE = 'movie'

# Existing library details
MOVIE_LIBRARY_NAME = u'- Film'
MOVIE_LIBRARY_FOLDERS = ['/mnt/plex/sorted/Movies']  # List of folders in library

# New trending library details
TRENDING_LIBRARY_NAME = 'Film - Trending'
# New folder to symlink existing items to
TRENDING_FOLDER = '/mnt/plex/local-sorted/Movies Popular/'
SORT_TITLE_FORMAT = u"{number} {title}"
MAX_AGE = 3  # Limit the age (in years) of items to be considered
             # (0 for no limit)
MAX_COUNT = 250  # Maximum number of items to keep in the library

# Weighted sorting (experimental)
WEIGHTED_SORTING = True
BETTER_RELEASE_DATE = False
# Think of these as percentages, but they don't have to add up to 1.0
# Higher value -> more important
WEIGHT_TRAKT_TREND = 0.75
WEIGHT_VOTE = 0.10
WEIGHT_AGE = 0.15
# Penalize (<0) or reward (>0) certain (TMDb) genres
WEIGHT_GENRE_BIAS = {
    'TV Movie': 0.7,
    'Animation': 0.95,
}

# The Movie Database details
# Enter your TMDb API key if your movie library is using
# "The Movie Database" agent.
# This will be used to convert the TMDb IDs to IMDB IDs.
# You can leave this blank '' if your movie library is using the
# "Plex Movie" agent.
TMDB_API_KEY = '3dbf8f9cbf5eb435446441aee6005d00'
TMDB_CACHE_FILE = '/tmp/tmdb_details.shelve'

# End config

TMDB_REQUEST_COUNT = 0  # DO NOT CHANGE


class colors(object):
    RED  = "\033[1;31m"
    BLUE = "\033[1;34m"
    CYAN = "\033[1;36m"
    GREEN = "\033[0;32m"
    RESET = "\033[0;0m"
    BOLD = "\033[;1m"
    REVERSE = "\033[;7m"


def create_trending_library(library_type='movie'):
    headers = {"X-Plex-Token": PLEX_TOKEN}
    params = {
        'name': TRENDING_LIBRARY_NAME,
        'language': 'en',
        'location': TRENDING_FOLDER
    }
    if library_type == 'movie':
        params['type'] = 'movie'
        params['agent'] = 'com.plexapp.agents.imdb'
        params['scanner'] = 'Plex Movie Scanner'
    elif library_type == 'tv':
        # FIXME
        raise NotImplemented()
    else:
        raise Exception("Library type should be 'movie' or 'tv'")

    url = '{base_url}/library/sections'.format(base_url=PLEX_URL)
    r = requests.post(url, headers=headers, params=params)


def add_sort_title(library_key, rating_key, number, title):
    headers = {'X-Plex-Token': PLEX_TOKEN}
    params = {
        'type': 1,
        'id': rating_key,
        'titleSort.value': SORT_TITLE_FORMAT.format(
            number=str(number).zfill(6), title=title),
        'titleSort.locked': 1,
    }

    url = "{base_url}/library/sections/{library}/all".format(
            base_url=PLEX_URL, library=library_key)
    r = requests.put(url, headers=headers, params=params)


def get_imdb_id_from_tmdb(tmdb_id, library_type='movie'):
    global TMDB_REQUEST_COUNT

    if not TMDB_API_KEY:
        return None

    if library_type not in ('movie', 'tv'):
        raise Exception("Library type should be 'movie' or 'tv'")

    # Wait 10 seconds for the TMDb rate limit
    if TMDB_REQUEST_COUNT >= 40:
        print(u"Waiting 10 seconds for the TMDb rate limit...")
        time.sleep(10)
        TMDB_REQUEST_COUNT = 0

    params = {"api_key": TMDB_API_KEY}

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
        return item.get('imdb_id')
    else:
        return None


def get_tmdb_details(tmdb_id, library_type='movie'):
    global TMDB_REQUEST_COUNT

    if library_type not in ('movie', 'tv'):
        raise Exception("Library type should be 'movie' or 'tv'")

    # Use cache
    cache = shelve.open(TMDB_CACHE_FILE)
    if cache.has_key(str(tmdb_id)) and \
            (cache[str(tmdb_id)]['cached'] + 3600 * 24) > int(time.time()):
        item = cache[str(tmdb_id)]
        cache.close()
        return item

    if not TMDB_API_KEY:
        cache.close()
        return None

    # Wait 10 seconds for the TMDb rate limit
    if TMDB_REQUEST_COUNT >= 40:
        print(u"Waiting 10 seconds for the TMDb rate limit...")
        time.sleep(10)
        TMDB_REQUEST_COUNT = 0

    params = {
        'api_key': TMDB_API_KEY,
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


def refresh_library(library, path):
    section = library.key
    e = dict(os.environ)
    e['LC_ALL'] = "en_US.UTF-8"
    e['PLEX_MEDIA_SERVER_MAX_PLUGIN_PROCS'] = "6"
    e['PLEX_MEDIA_SERVER_TMPDIR'] = "/tmp"
    e['PLEX_MEDIA_SERVER_HOME'] = PLEX_HOME_DIR
    e['LD_LIBRARY_PATH'] = PLEX_HOME_DIR
    print(u"Scanning {path}".format(path=path))
    subprocess.call([PLEX_MEDIA_SCANNER_PATH, '--scan',
                     '--refresh', '--section', section, '--directory', path],
                    env=e)


def weighted_sorting(item_list):
    def _get_non_theatrical_release(release_dates):
        # Returns earliest release date that is not theatrical
        types = {}
        for country in release_dates.get('results', []):
            # FIXME Look at others too?
            if country['iso_3166_1'] != 'US':
                continue
            for d in country['release_dates']:
                if d['type'] in (4, 5, 6):
                    # 4: Digital, 5: Physical, 6: TV
                    types[str(d['type'])] = datetime.datetime.strptime(
                        d['release_date'], '%Y-%m-%dT%H:%M:%S.%fZ').date()
            break

        release_date = None
        for t, d in types.items():
            if not release_date or d < release_date:
                release_date = d

        return release_date

    def _get_age_weight(days):
        # Everything younger than this will get 1
        min_days = 100
        # Everything older than this will get 0
        max_days = float(MAX_AGE) / 4.0 * 365.25 or 200
        if days <= min_days:
            return 1
        elif days >= max_days:
            return 0
        else:
            return 1 - (days - min_days) / (max_days - min_days)

    total_items = len(item_list)

    # TMDB details
    today = datetime.date.today()
    total_tmdb_vote = 0.0
    tmdb_votes = []
    for i, m in enumerate(item_list):
        details = get_tmdb_details(m['tmdb_id'])
        m['tmdb_popularity'] = float(details['popularity'])
        m['tmdb_vote'] = float(details['vote_average'])
        m['tmdb_vote_count'] = int(details['vote_count'])
        if BETTER_RELEASE_DATE:
            m['release_date'] = _get_non_theatrical_release(
                details['release_dates']) or \
                datetime.datetime.strptime(details['release_date'],
                '%Y-%m-%d').date()
        else:
            m['release_date'] = datetime.datetime.strptime(
                details['release_date'], '%Y-%m-%d').date()
        m['original_idx'] = i + 1
        m['genres'] = [g['name'].lower() for g in details['genres']]
        item_age_td = today - m['release_date']
        m['age'] = item_age_td.days
        if m['tmdb_vote_count'] > 150 or m['age'] > 50:
            tmdb_votes.append(m['tmdb_vote'])
        total_tmdb_vote += m['tmdb_vote']
        item_list[i] = m
    average_tmdb_vote = total_tmdb_vote / float(total_items)

    tmdb_votes.sort()

    for i, m in enumerate(item_list):
        # Distribute all weights evenly from 0 to 1 (times global factor)
        # More weight means it'll go higher in the final list
        index_weight = float(total_items - i) / float(total_items)
        if m['tmdb_vote_count'] > 150 or m['age'] > 50:
            vote_weight = (tmdb_votes.index(m['tmdb_vote']) + 1) / float(len(tmdb_votes))
        else:
            # Assume below average rating for new/less voted items
            vote_weight = 0.25
        age_weight = _get_age_weight(float(m['age']))
        weight = (index_weight * WEIGHT_TRAKT_TREND
                  + vote_weight * WEIGHT_VOTE
                  + age_weight * WEIGHT_AGE)
        for genre, value in WEIGHT_GENRE_BIAS.items():
            if genre.lower() in m['genres']:
                weight *= value
        m['index_weight'] = index_weight
        m['vote_weight'] = vote_weight
        m['age_weight'] = age_weight
        m['weight'] = weight
        item_list[i] = m

    item_list.sort(key = lambda m: m['weight'], reverse=True)

    for i, m in enumerate(item_list):
        if (i+1) < m['original_idx']:
            net = colors.GREEN + u'↑'
        elif (i+1) > m['original_idx']:
            net = colors.RED + u'↓'
        else:
            net = u' '
        net += str(abs(i + 1 - m['original_idx'])).rjust(3)
        print(u"{} {:>3}: trnd:{:>3}, w_trnd:{:0<5}; vote:{}, w_vote:{:0<5}; "
            "age:{:>4}, w_age:{:0<5}; w_cmb:{:0<5}; {} {}{}".format(
                net, i+1, m['original_idx'], round(m['index_weight'], 3),
                m['tmdb_vote'], round(m['vote_weight'], 3), m['age'],
                round(m['age_weight'], 3), round(m['weight'], 3),
                m['title'].encode('utf8'), m['year'], colors.RESET))

    return item_list


def run_trakt_watched_sort_only():
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    except:
        print(u"No Plex server found at: {base_url}".format(base_url=PLEX_URL))
        print(u"Exiting script.")
        return 0

    trakt.init(TRAKT_USERNAME, client_id=TRAKT_CLIENT_ID,
               client_secret=TRAKT_CLIENT_SECRET)
    trakt_core = trakt.core.Core()
    item_list = []
    item_ids = []
    curyear = datetime.datetime.now().year

    def _add_from_trakt_list(url):
        print(u"Retrieving the trakt list: {}".format(url))
        movie_data = trakt_core._handle_request('get', url)
        for m in movie_data:
            # Skip already added movies
            if m['movie']['ids']['imdb'] in item_ids:
                continue
            # Skip old movies
            if MAX_AGE != 0 \
                    and (curyear - (MAX_AGE - 1)) > int(m['movie']['year']):
                continue
            item_list.append({
                'id': m['movie']['ids']['imdb'],
                'tmdb_id': m['movie']['ids']['tmdb'],
                'title': m['movie']['title'].encode('utf8'),
                'year': m['movie']['year'],
            })
            item_ids.append(m['movie']['ids']['imdb'])
            print(u"{} {} {}".format(
                len(item_list), m['movie']['title'], m['movie']['year']))

    # Get the trakt lists
    for url in TRAKT_LIST_URLS:
        _add_from_trakt_list(url)

    trending_library = plex.library.section(TRENDING_LIBRARY_NAME)
    trending_library_key = trending_library.key
    all_trending_movies = trending_library.all()

    if WEIGHTED_SORTING:
        if TMDB_API_KEY:
            item_list = weighted_sorting(item_list)
        else:
            print(u"TMDd API key is required for weighted sorting")

    # Create a dictionary of {imdb_id: movie}
    imdb_map = {}
    for m in all_trending_movies:
        if m.guid != None and 'imdb://' in m.guid:
            imdb_id = m.guid.split('imdb://')[1].split('?')[0]
        elif m.guid != None and 'themoviedb://' in m.guid:
            tmdb_id = m.guid.split('themoviedb://')[1].split('?')[0]
            imdb_id = get_imdb_id_from_tmdb(tmdb_id)
        else:
            imdb_id = None

        if imdb_id and imdb_id in item_ids:
            imdb_map[imdb_id] = m
        else:
            imdb_map[m.ratingKey] = m

    # Modify the sort title to match the trakt watched order
    print(u"Setting the sort titles for the '{}' library...".format(
        TRENDING_LIBRARY_NAME))
    in_library_idx = []
    i = 0
    for m in item_list:
        movie = imdb_map.pop(m['id'], None)
        if movie:
            i += 1
            add_sort_title(trending_library_key, movie.ratingKey, i,
                           m['title'])
            in_library_idx.append(i)


def run_trakt_watched():
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    except:
        print(u"No Plex server found at: {base_url}".format(base_url=PLEX_URL))
        print(u"Exiting script.")
        return 0

    trakt.init(TRAKT_USERNAME, client_id=TRAKT_CLIENT_ID,
               client_secret=TRAKT_CLIENT_SECRET)
    trakt_core = trakt.core.Core()
    item_list = []
    item_ids = []
    curyear = datetime.datetime.now().year

    def _add_from_trakt_list(url):
        print(u"Retrieving the trakt list: {}".format(url))
        movie_data = trakt_core._handle_request('get', url)
        for m in movie_data:
            # Skip already added movies
            if m['movie']['ids']['imdb'] in item_ids:
                continue
            # Skip old movies
            if MAX_AGE != 0 and \
                    (curyear - (MAX_AGE - 1)) > int(m['movie']['year']):
                continue
            item_list.append({
                'id': m['movie']['ids']['imdb'],
                'tmdb_id': m['movie']['ids']['tmdb'],
                'title': m['movie']['title'],
                'year': m['movie']['year'],
            })
            item_ids.append(m['movie']['ids']['imdb'])

    # Get the trakt lists
    for url in TRAKT_LIST_URLS:
        _add_from_trakt_list(url)

    # Get list of movies from the Plex server
    print(u"Trying to match with movies from the '{library}' library ".format(
        library=MOVIE_LIBRARY_NAME))
    try:
        movie_library = plex.library.section(MOVIE_LIBRARY_NAME)
        #all_movies = movie_library.all()
    except:
        print(u"The '{library}' library does not exist in Plex.".format(
            library=MOVIE_LIBRARY_NAME))
        print(u"Exiting script.")
        return 0

    # Create a list of matching movies
    matching_movies = []
    nonmatching_idx = []
    for i, m in enumerate(item_list):
        if len(matching_movies) >= MAX_COUNT:
            nonmatching_idx.append(i)
            continue
        try:
            res = movie_library.search(title=m['title'], year=m['year'])
            if not res:
                res = movie_library.search(title=m['title'], year=int(m['year'])+1)
            if not res:
                res = movie_library.search(title=m['title'], year=int(m['year'])-1)
        except KeyError:
            print(u"Warning: Unable to look for '{} ({})', skipping.".format(
                m['title'], m['year']))
            res = None
        if res:
            for r in res:
                imdb_id = None
                tmdb_id = None
                if r.guid != None and 'imdb://' in r.guid:
                    imdb_id = r.guid.split('imdb://')[1].split('?')[0]
                elif r.guid != None and 'themoviedb://' in r.guid:
                    tmdb_id = r.guid.split('themoviedb://')[1].split('?')[0]

                if imdb_id and imdb_id == m['id']:
                    matching_movies.append(r)
                    print(u"{} {} {}".format(
                        len(matching_movies), m['title'], m['year']))
                    break
                elif tmdb_id and tmdb_id == m['tmdb_id']:
                    matching_movies.append(r)
                    print(u"{} {} {}".format(
                        len(matching_movies), m['title'], m['year']))
                    break
            else:
                nonmatching_idx.append(i)
        if not res:
            nonmatching_idx.append(i)

    for i in reversed(nonmatching_idx):
        del item_list[i]
        del item_ids[i]

    # Create symlinks for all movies in your library on the trakt watched
    print(u"Creating symlinks for {count} matching movies in the "
          u"library...".format(count=len(matching_movies)))

    try:
        if not os.path.exists(TRENDING_FOLDER):
            os.mkdir(TRENDING_FOLDER)
    except:
        print(u"Unable to create the trending library folder "
              u"'{folder}'.".format(folder=TRENDING_FOLDER))
        print(u"Exiting script.")
        return 0

    count = 0
    updated_paths = []
    for movie in matching_movies:
        for part in movie.iterParts():
            old_path_file = part.file.encode('UTF-8')
            old_path, file_name = os.path.split(old_path_file)

            folder_name = ''
            for f in MOVIE_LIBRARY_FOLDERS:
                f = os.path.abspath(f)
                if old_path.lower().startswith(f.lower()):
                    folder_name = os.path.relpath(old_path, f)

            if folder_name == '.':
                new_path = os.path.join(TRENDING_FOLDER, file_name)
                dir = False
            else:
                new_path = os.path.join(TRENDING_FOLDER, folder_name)
                dir = True
                parent_path = os.path.dirname(os.path.abspath(new_path))
                if not os.path.exists(parent_path):
                    try:
                        os.makedirs(parent_path)
                    except OSError as e:
                        if e.errno == errno.EEXIST and \
                                os.path.isdir(parent_path):
                            pass
                        else:
                            raise
                # Clean up old, empty directories
                if os.path.exists(new_path) and not os.listdir(new_path):
                    os.rmdir(new_path)

            if (dir and not os.path.exists(new_path)) or \
                    (not dir and not os.path.isfile(new_path)):
                try:
                    if os.name == 'nt':
                        if dir:
                            subprocess.call(['mklink', '/D', new_path,
                                             old_path], shell=True)
                        else:
                            subprocess.call(['mklink', new_path,
                                             old_path_file], shell=True)
                    else:
                        if dir:
                            os.symlink(old_path, new_path)
                        else:
                            os.symlink(old_path_file, new_path)
                    count += 1
                    updated_paths.append(new_path)
                except Exception as e:
                    print(u"Symlink failed for {path}: {e}".format(
                        path=new_path, e=e))

    print(u"Created symlinks for {count} movies.".format(count=count))

    # Check if the trakt watched library exists in Plex
    print(u"Creating the '{}' library in Plex...".format(
        TRENDING_LIBRARY_NAME))
    try:
        trending_library = plex.library.section(TRENDING_LIBRARY_NAME)
        trending_library_key = trending_library.key
        print(u"Library already exists in Plex. Refreshing the library...")

        trending_library.update()
        #for path in updated_paths:
        #    refresh_library(trending_library, path)
    except:
        create_trending_library()
        trending_library = plex.library.section(TRENDING_LIBRARY_NAME)
        trending_library_key = trending_library.key

    if WEIGHTED_SORTING:
        # While we wait for refresh, query TMDb etc.
        if TMDB_API_KEY:
            print(u"Getting data from TMDb to add weighted sorting...")
            item_list = weighted_sorting(item_list)
        else:
            print(u"TMDd API key is required for weighted sorting")

    # Wait for metadata to finish downloading before continuing
    print(u"Waiting for metadata to finish downloading...")
    trending_library = plex.library.section(TRENDING_LIBRARY_NAME)
    while trending_library.refreshing:
        time.sleep(5)
        trending_library = plex.library.section(TRENDING_LIBRARY_NAME)

    #time.sleep(5)

    # Retrieve a list of movies from the trakt watched library
    print(u"Retrieving a list of movies from the '{library}' library in "
          u"Plex...".format(library=TRENDING_LIBRARY_NAME))
    all_trending_movies = trending_library.all()

    # Create a dictionary of {imdb_id: movie}
    imdb_map = {}
    for m in all_trending_movies:
        if m.guid != None and 'imdb://' in m.guid:
            imdb_id = m.guid.split('imdb://')[1].split('?')[0]
        elif m.guid != None and 'themoviedb://' in m.guid:
            tmdb_id = m.guid.split('themoviedb://')[1].split('?')[0]
            imdb_id = get_imdb_id_from_tmdb(tmdb_id)
        else:
            imdb_id = None

        if imdb_id and imdb_id in item_ids:
            imdb_map[imdb_id] = m
        else:
            imdb_map[m.ratingKey] = m

    # Modify the sort title to match the trakt watched order
    print(u"Setting the sort titles for the '{}' library...".format(
        TRENDING_LIBRARY_NAME))
    in_library_idx = []
    i = 0
    for m in item_list:
        movie = imdb_map.pop(m['id'], None)
        if movie:
            i += 1
            add_sort_title(trending_library_key, movie.ratingKey, i, m['title'])
            in_library_idx.append(i)

    # Remove movies from library with are no longer on the trakt watched list
    print(u"Removing symlinks for movies which are not on the trakt watched "
          u"list...".format(library=TRENDING_LIBRARY_NAME))
    count = 0
    updated_paths = []
    for movie in imdb_map.values():
        for part in movie.iterParts():
            old_path_file = part.file.encode('UTF-8')
            old_path, file_name = os.path.split(old_path_file)

            folder_name = os.path.relpath(old_path, TRENDING_FOLDER)

            if folder_name == '.':
                new_path = os.path.join(TRENDING_FOLDER, file_name)
                dir = False
            else:
                new_path = os.path.join(TRENDING_FOLDER, folder_name)
                dir = True

            if (dir and os.path.exists(new_path)) or \
                    (not dir and os.path.isfile(new_path)):
                try:
                    if os.name == 'nt':
                        if dir:
                            os.rmdir(new_path)
                        else:
                            os.remove(new_path)
                    else:
                        os.unlink(new_path)
                    count += 1
                    updated_paths.append(new_path)
                except Exception as e:
                    print(u"Remove symlink failed for {path}: {e}".format(
                        path=new_path, e=e))

    print(u"Removed symlinks for {count} movies.".format(count=count))

    # Refresh the library to clean up the deleted movies
    print(u"Refreshing the '{library}' library...".format(
        library=TRENDING_LIBRARY_NAME))
    trending_library.update()
    time.sleep(10)
    trending_library = plex.library.section(TRENDING_LIBRARY_NAME)
    while trending_library.refreshing:
        time.sleep(5)
        trending_library = plex.library.section(TRENDING_LIBRARY_NAME)
    trending_library.emptyTrash()

    return len(item_ids)


if __name__ == "__main__":
    if '--sort-only' in sys.argv:
        run_trakt_watched_sort_only()
    else:
        list_count = run_trakt_watched()
        print(u"Number of movies in the library: {count}".format(
            count=list_count))

    print(u"Done!")

