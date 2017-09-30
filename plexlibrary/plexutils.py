# -*- coding: utf-8 -*-
import requests


def add_sort_title(library_key, rating_key, number, title, library_type, title_format, visible=False):
    headers = {'X-Plex-Token': config.PLEX_TOKEN}
    if library_type == 'movie':
        search_type = 1
    elif library_type == 'tv':
        search_type = 2
    params = {
        'type': search_type,
        'id': rating_key,
        'titleSort.value': title_format.format(
            number=str(number).zfill(6), title=title),
        'titleSort.locked': 1,
    }

    if set_title:
        params['title.value'] = title_format.format(
            number=str(number), title=title)
        params['title.locked'] = 1
    else:
        params['title.value'] = title=title
        params['title.locked'] = 0

    url = "{base_url}/library/sections/{library}/all".format(
            base_url=config.PLEX_URL, library=library_key)
    r = requests.put(url, headers=headers, params=params)


def create_new_library(name, folder, library_type='movie'):
    headers = {"X-Plex-Token": config.PLEX_TOKEN}
    params = {
        'name': name,
        'language': 'en',
        'location': folder,
    }
    if library_type == 'movie':
        params['type'] = 'movie'
        params['agent'] = 'com.plexapp.agents.imdb'
        params['scanner'] = 'Plex Movie Scanner'
    elif library_type == 'tv':
        params['type'] = 'tv'
        params['agent'] = 'com.plexapp.agents.tvdb'  # FIXME?
        params['scanner'] = 'TheTVDB'
    else:
        raise Exception("Library type should be 'movie' or 'tv'")

    url = '{base_url}/library/sections'.format(base_url=config.PLEX_URL)
    r = requests.post(url, headers=headers, params=params)

