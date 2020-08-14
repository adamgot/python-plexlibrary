# -*- coding: utf-8 -*-
import datetime

import requests
from lxml import html

import logs
from utils import add_years


class IMDb(object):
    def __init__(self, tmdb, tvdb):
        self.tmdb = tmdb
        self.tvdb = tvdb

    def _handle_request(self, url):
        """Stolen from Automated IMDB Top 250 Plex library script
           by /u/SwiftPanda16
        """
        r = requests.get(url)
        tree = html.fromstring(r.content)

        # Dict of the IMDB top 250 ids in order
        titles = tree.xpath("//table[contains(@class, 'chart')]"
                            "//td[@class='titleColumn']/a/text()")
        years = tree.xpath("//table[contains(@class, 'chart')]"
                           "//td[@class='titleColumn']/span/text()")
        ids = tree.xpath("//table[contains(@class, 'chart')]"
                         "//td[@class='ratingColumn']/div//@data-titleid")

        return ids, titles, years

    def add_movies(self, url, movie_list=None, movie_ids=None, max_age=0):
        if not movie_list:
            movie_list = []
        if not movie_ids:
            movie_ids = []
        max_date = add_years(max_age * -1)
        logs.info(u"Retrieving the IMDB list: {}".format(url))

        (imdb_ids, imdb_titles, imdb_years) = self._handle_request(url)
        for i, imdb_id in enumerate(imdb_ids):
            # Skip already added movies
            if imdb_id in movie_ids:
                continue

            if self.tmdb:
                tmdb_data = self.tmdb.get_tmdb_from_imdb(imdb_id, 'movie')

            if tmdb_data and tmdb_data['release_date']:
                date = datetime.datetime.strptime(tmdb_data['release_date'],
                                                  '%Y-%m-%d')
            elif imdb_years[i]:
                date = datetime.datetime(int(str(imdb_years[i]).strip("()")),
                                     12, 31)
            else:
                date = datetime.date.today()

            # Skip old movies
            if max_age != 0 and (max_date > date):
                continue
            movie_list.append({
                'id': imdb_id,
                'tmdb_id': tmdb_data['id'] if tmdb_data else None,
                'title': tmdb_data['title'] if tmdb_data else imdb_titles[i],
                'year': date.year,
            })
            movie_ids.append(imdb_id)
            if tmdb_data and tmdb_data['id']:
                movie_ids.append('tmdb' + str(tmdb_data['id']))

        return movie_list, movie_ids

    def add_shows(self, url, show_list=None, show_ids=None, max_age=0):
        if not show_list:
            show_list = []
        if not show_ids:
            show_ids = []
        curyear = datetime.datetime.now().year
        logs.info(u"Retrieving the IMDb list: {}".format(url))
        data = {}
        if max_age != 0:
            data['extended'] = 'full'
        (imdb_ids, imdb_titles, imdb_years) = self._handle_request(url)
        for i, imdb_id in enumerate(imdb_ids):
            # Skip already added shows
            if imdb_id in show_ids:
                continue

            if self.tvdb:
                tvdb_data = self.tvdb.get_tvdb_from_imdb(imdb_id)

            if self.tmdb:
                tmdb_data = self.tmdb.get_tmdb_from_imdb(imdb_id, 'tv')

            if tvdb_data and tvdb_data['firstAired'] != "":
                year = datetime.datetime.strptime(tvdb_data['firstAired'],
                                                  '%Y-%m-%d').year
            elif tmdb_data and tmdb_data['first_air_date'] != "":
                year = datetime.datetime.strptime(tmdb_data['first_air_date'],
                                                  '%Y-%m-%d').year
            elif imdb_years[i]:
                year = str(imdb_years[i]).strip("()")
            else:
                year = datetime.date.today().year

            # Skip old shows
            if max_age != 0 \
                    and (curyear - (max_age - 1)) > year:
                continue

            if tvdb_data:
                title = tvdb_data['seriesName']
            else:
                title = tmdb_data['name'] if tmdb_data else imdb_titles[i]

            show_list.append({
                'id': imdb_id,
                'tvdb_id': tvdb_data['id'] if tvdb_data else None,
                'tmdb_id': tmdb_data['id'] if tmdb_data else None,
                'title': title,
                'year': year,
            })
            show_ids.append(imdb_id)
            if tmdb_data and tmdb_data['id']:
                show_ids.append('tmdb' + str(tmdb_data['id']))
            if tvdb_data and tvdb_data['id']:
                show_ids.append('tvdb' + str(tvdb_data['id']))

        return show_list, show_ids

    def add_items(self, item_type, url, item_list=None, item_ids=None,
                  max_age=0):
        if item_type == 'movie':
            return self.add_movies(url, movie_list=item_list,
                                   movie_ids=item_ids, max_age=max_age)
        elif item_type == 'tv':
            return self.add_shows(url, show_list=item_list,
                                  show_ids=item_ids, max_age=max_age)
