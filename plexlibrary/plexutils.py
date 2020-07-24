# -*- coding: utf-8 -*-
import plexapi.server
import plexapi.media
import requests
from urllib.parse import urlencode
from typing import List


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

    def create_new_playlist(self, playlist_name, items: List[plexapi.media.Media]):
        self.server.createPlaylist(title=playlist_name, items=items)

    def _get_existing_playlist(self, playlist_name):
        for playlist in self.server.playlists():
            if playlist.title == playlist_name:
                return playlist
        return None

    def get_playlist_items(self, playlist_name):
        playlist = self._get_existing_playlist(playlist_name=playlist_name)
        if playlist:
            return playlist.items()
        return []

    def add_to_playlist(self, playlist_name, items: List[plexapi.media.Media]):
        playlist = self._get_existing_playlist(playlist_name=playlist_name)
        if playlist:
            playlist.addItems(items=items)
        else:
            self.create_new_playlist(playlist_name=playlist_name, items=items)

    def remove_from_playlist(self, playlist_name, items: List[plexapi.media.Media]):
        playlist = self._get_existing_playlist(playlist_name=playlist_name)
        if playlist:
            for item in items:
                playlist.removeItem(item=item)

    def reset_playlist(self, playlist_name, new_items: List[plexapi.media.Media]):
        """
        Delete old playlist and remake it with new items
        :param new_items: list of Media objects
        :param playlist_name:
        :return:
        """
        playlist = self._get_existing_playlist(playlist_name=playlist_name)
        if playlist:
            playlist.delete()
        self.create_new_playlist(playlist_name=playlist_name, items=new_items)

    def _get_section_by_name(self, section_name):
        try:
            return self.server.library.section(title=section_name)
        except:
            pass
        return None

    def get_library_paths(self, library_name):
        section = self._get_section_by_name(section_name=library_name)
        if section:
            return section.locations
        return []

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
