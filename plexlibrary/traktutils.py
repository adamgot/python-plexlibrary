# -*- coding: utf-8 -*-
import datetime

import trakt


class Trakt(object):
    def __init__(self, username, client_id='', client_secret=''):
        trakt.init(username, client_id=client_id, client_secret=client_secret)
        self.trakt = trakt
        self.trakt_core = trakt.core.Core()

    def add_movies(self, url, movie_list=None, movie_ids=None, max_age=0):
        if not movie_list:
            movie_list = []
        if not movie_ids:
            movie_ids = []
        curyear = datetime.datetime.now().year
        print(u"Retrieving the trakt list: {}".format(url))
        movie_data = self.trakt_core._handle_request('get', url)
        for m in movie_data:
            # Skip already added movies
            if m['movie']['ids']['imdb'] in movie_ids:
                continue
            # Skip old movies
            if max_age != 0 \
                    and (curyear - (max_age - 1)) > int(m['movie']['year']):
                continue
            movie_list.append({
                'id': m['movie']['ids']['imdb'],
                'tmdb_id': m['movie']['ids'].get('tmdb', ''),
                'title': m['movie']['title'],
                'year': m['movie']['year'],
            })
            movie_ids.append(m['movie']['ids']['imdb'])
            if m['movie']['ids'].get('tmdb'):
                movie_ids.append('tmdb' + str(m['movie']['ids']['tmdb']))
            else:
                force_imdb_id_match = True

        return (movie_list, movie_ids)

    def add_shows(self, url, show_list=None, show_ids=None, max_age=0):
        if not show_list:
            show_list = []
        if not show_ids:
            show_ids = []
        curyear = datetime.datetime.now().year
        print(u"Retrieving the trakt list: {}".format(url))
        show_data = self.trakt_core._handle_request('get', url)
        for m in show_data:
            # Skip already added shows
            if m['show']['ids']['imdb'] in show_ids:
                continue
            # Skip old shows
            if max_age != 0 \
                    and (curyear - (max_age - 1)) > int(m['show']['year']):
                continue
            show_list.append({
                'id': m['show']['ids']['imdb'],
                'tmdb_id': m['show']['ids'].get('tmdb', ''),
                'tvdb_id': m['show']['ids'].get('tvdb', ''),
                'title': m['show']['title'],
                'year': m['show']['year'],
            })
            show_ids.append(m['show']['ids']['imdb'])
            if m['show']['ids'].get('tmdb'):
                show_ids.append('tmdb' + str(m['show']['ids']['tmdb']))
            else:
                force_imdb_id_match = True
            if m['show']['ids'].get('tvdb'):
                show_ids.append('tvdb' + str(m['show']['ids']['tvdb']))
            else:
                force_imdb_id_match = True

        return (show_list, show_ids)

    def add_items(self, item_type, url, item_list=None, item_ids=None, max_age=0):
        if item_type == 'movie':
            return self.add_movies(url, movie_list=item_list,
                                   movie_ids=item_ids, max_age=max_age)
        elif item_type == 'tv':
            return self.add_shows(url, show_list=item_list,
                                  show_ids=item_ids, max_age=max_age)

