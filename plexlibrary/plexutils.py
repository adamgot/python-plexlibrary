# -*- coding: utf-8 -*-
import plexapi.server
import plexapi.media
import requests
import time
from typing import List

import logs


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
        
    def _user_has_access(self, user):
        for server in user.servers:
            if server.machineIdentifier == self.server.machineIdentifier:
                return True
        return False

    def _get_plex_instance_for_user(self, user):
        if self._user_has_access(user):
            return Plex(baseurl=self.baseurl, token=self.server.myPlexAccount().user(user.username).get_token(
                self.server.machineIdentifier))
        return None

    def _get_all_users(self):
        return self.server.myPlexAccount().users()

    def _get_specific_users(self, user_names: List):
        users = []
        for user in self._get_all_users():
            if user.username in user_names:
                users.append(user)
        return users

    def _create_new_playlist(self, playlist_name, items: List[plexapi.media.Media]):
        self.server.createPlaylist(title=playlist_name, items=items)

    def _get_existing_playlist(self, playlist_name, user_name: str = None):
        if user_name:
            users = self._get_specific_users(user_names=[user_name])
            if users:
                user_server = self._get_plex_instance_for_user(user=users[0])
                if user_server:
                    return user_server._get_existing_playlist(playlist_name=playlist_name)
                else:
                    logs.info(f"{user_name} does not have access to your server.")
        else:
            for playlist in self.server.playlists():
                if playlist.title == playlist_name:
                    return playlist
        return None

    def get_playlist_items(self, playlist_name, user_name: str = None):
        playlist = self._get_existing_playlist(playlist_name=playlist_name, user_name=user_name)
        if playlist:
            return playlist.items()
        return []

    def add_to_playlist_for_users(self, playlist_name, items: List[plexapi.media.Media], user_names: List = None,
                                  all_users: bool = False):
        users = []
        if all_users:
            users = self._get_all_users()
        elif user_names:
            users = self._get_specific_users(user_names=user_names)
        # add on admin account
        self.add_to_playlist(playlist_name=playlist_name, items=items)
        # add for all other users
        for user in users:
            logs.info("Adding items to {user_name}'s {list_name} playlist".format(user_name=user.username,
                                                                                  list_name=playlist_name))
            user_server = self._get_plex_instance_for_user(user=user)
            if user_server:
                user_server.add_to_playlist(playlist_name=playlist_name, items=items)
            else:
                logs.info(f"{user.username} does not have access to your server.")

    def add_to_playlist(self, playlist_name, items: List[plexapi.media.Media]):
        playlist = self._get_existing_playlist(playlist_name=playlist_name)
        if playlist:
            playlist.addItems(items=items)
        else:
            self._create_new_playlist(playlist_name=playlist_name, items=items)

    def remove_from_playlist_for_users(self, playlist_name, items: List[plexapi.media.Media], user_names: List = None,
                                       all_users: bool = False):
        users = []
        if all_users:
            users = self._get_all_users()
        elif user_names:
            users = self._get_specific_users(user_names=user_names)
        # remove on admin account
        self.remove_from_playlist(playlist_name=playlist_name, items=items)
        # remove for all other users
        for user in users:
            logs.info("Removing items from {user_name}'s {list_name} playlist".format(user_name=user.username,
                                                                                      list_name=playlist_name))
            user_server = self._get_plex_instance_for_user(user=user)
            if user_server:
                user_server.remove_from_playlist(playlist_name=playlist_name, items=items)
            else:
                logs.info(f"{user.username} does not have access to your server.")


    def remove_from_playlist(self, playlist_name, items: List[plexapi.media.Media]):
        playlist = self._get_existing_playlist(playlist_name=playlist_name)
        if playlist:
            for item in items:
                playlist.removeItem(item=item)

    def reset_playlist(self, playlist_name, new_items: List[plexapi.media.Media], user_names: List = None,
                       all_users: bool = False):
        """
        Delete old playlist and remake it with new items
        :param user_names: Make change for specific users, ["name", "name2", "name3"]
        :param all_users: Make change for all users
        :param new_items: list of Media objects
        :param playlist_name:
        :return:
        """
        users = []
        if all_users:
            users = self._get_all_users()
        elif user_names:
            users = self._get_specific_users(user_names=user_names)
        if users:  # recursively reset for self and for each user
            self.reset_playlist(playlist_name=playlist_name, new_items=new_items)
            for user in users:
                logs.info("Resetting {list_name} playlist for {user_name}".format(list_name=playlist_name,
                                                                                  user_name=user.username))
                user_server = self._get_plex_instance_for_user(user=user)
                if user_server:
                    user_server.reset_playlist(playlist_name=playlist_name, new_items=new_items)
                else:
                    logs.info(f"{user.username} does not have access to your server.")

        else:
            playlist = self._get_existing_playlist(playlist_name=playlist_name)
            if playlist:
                playlist.delete()
            self._create_new_playlist(playlist_name=playlist_name, items=new_items)

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
