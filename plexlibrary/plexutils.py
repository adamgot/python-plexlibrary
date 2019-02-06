# -*- coding: utf-8 -*-
import plexapi.server
import requests


class Plex(object):
    def __init__(self, baseurl, token):
        self.baseurl = baseurl
        self.token = token
        try:
            self.server = plexapi.server.PlexServer(
                baseurl=baseurl, token=token)
        except:
            raise Exception("No Plex server found at: {base_url}".format(
                base_url=baseurl))

    def create_new_library(self, name, folder, library_type='movie'):
        headers = {"X-Plex-Token": self.token}
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
            params['type'] = 'show'
            params['agent'] = 'com.plexapp.agents.thetvdb'
            params['scanner'] = 'Plex Series Scanner'
        else:
            raise Exception("Library type should be 'movie' or 'tv'")

        url = '{base_url}/library/sections'.format(base_url=self.baseurl)
        requests.post(url, headers=headers, params=params)

    def set_sort_title(self, library_key, rating_key, number, title,
                       library_type, title_format, visible=False):
        headers = {'X-Plex-Token': self.token}
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

        if visible:
            params['title.value'] = title_format.format(
                number=str(number), title=title)
            params['title.locked'] = 1
        else:
            params['title.value'] = title
            params['title.locked'] = 0

        url = "{base_url}/library/sections/{library}/all".format(
                base_url=self.baseurl, library=library_key)
        requests.put(url, headers=headers, params=params)
