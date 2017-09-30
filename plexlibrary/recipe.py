# -*- coding: utf-8 -*-
"""recipe
"""

import datetime
import importlib
import json
import os
import random
import shelve
import subprocess
import sys
import time

import plexapi.server
import requests
import trakt
import yaml

from colors import Colors
import plexutils
import tmdb


class Recipe(object):
    def __init__(self, recipe_name, sory_only=False):
        self.recipe_name = recipe_name

        # TODO Anything but this
        parent_dir = (os.path.abspath(os.path.join(os.path.dirname(__file__),
            os.path.pardir)))
        sys.path.append(parent_dir)
        self.recipe = importlib.import_module('recipes.' + recipe_name)
        sys.path.remove(parent_dir)

        with open(os.path.join(parent_dir, 'config.yml'), 'r') as ymlfile:
            self.config = yaml.load(ymlfile)

        if self.recipe.LIBRARY_TYPE.lower().startswith('movie'):
            self.library_type = 'movie'
        elif self.recipe.LIBRARY_TYPE.lower().startswith('tv'):
            self.library_type = 'tv'
        else:
            raise Exception("Library type should be 'movie' or 'tv'")

        try:
            self.plex = plexapi.server.PlexServer(**self.config['plex'])
        except:
            raise Exception("No Plex server found at: {base_url}".format(
                base_url=self.config['plex']['baseurl']))

    def weighted_sorting(self, item_list, recipe, library_type):
        def _get_non_theatrical_release(release_dates):
            # Returns earliest release date that is not theatrical
            # TODO PREDB
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
            if library_type == 'movie':
                # Everything younger than this will get 1
                min_days = 100
                # Everything older than this will get 0
                max_days = float(recipe.MAX_AGE) / 4.0 * 365.25 or 200
            else:
                min_days = 14
                max_days = float(recipe.MAX_AGE) / 4.0 * 365.25 or 100
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
            m['original_idx'] = i + 1
            details = tmdb.get_details(m['tmdb_id'], library_type)
            if not details:
                print(u"Warning: No TMDb data for {}".format(m['title']))
                continue
            m['tmdb_popularity'] = float(details['popularity'])
            m['tmdb_vote'] = float(details['vote_average'])
            m['tmdb_vote_count'] = int(details['vote_count'])
            if library_type == 'movie':
                if recipe.BETTER_RELEASE_DATE:
                    m['release_date'] = _get_non_theatrical_release(
                        details['release_dates']) or \
                        datetime.datetime.strptime(details['release_date'],
                        '%Y-%m-%d').date()
                else:
                    m['release_date'] = datetime.datetime.strptime(
                        details['release_date'], '%Y-%m-%d').date()
                item_age_td = today - m['release_date']
            elif library_type == 'tv':
                m['last_air_date'] = datetime.datetime.strptime(
                    details['last_air_date'], '%Y-%m-%d').date()
                item_age_td = today - m['last_air_date']
            m['genres'] = [g['name'].lower() for g in details['genres']]
            m['age'] = item_age_td.days
            if library_type == 'tv' or m['tmdb_vote_count'] > 150 or m['age'] > 50:
                tmdb_votes.append(m['tmdb_vote'])
            total_tmdb_vote += m['tmdb_vote']
            item_list[i] = m
        average_tmdb_vote = total_tmdb_vote / float(total_items)

        tmdb_votes.sort()

        for i, m in enumerate(item_list):
            # Distribute all weights evenly from 0 to 1 (times global factor)
            # More weight means it'll go higher in the final list
            index_weight = float(total_items - i) / float(total_items)
            m['index_weight'] = index_weight * recipe.WEIGHT_INDEX
            if m.get('tmdb_popularity'):
                if library_type == 'tv' or m.get('tmdb_vote_count') > 150 or m['age'] > 50:
                    vote_weight = (tmdb_votes.index(m['tmdb_vote']) + 1) / float(len(tmdb_votes))
                else:
                    # Assume below average rating for new/less voted items
                    vote_weight = 0.25
                age_weight = _get_age_weight(float(m['age']))

                if hasattr(recipe, 'WEIGHT_RANDOM'):
                    random_weight = random.random()
                    m['random_weight'] = random_weight * recipe.WEIGHT_RANDOM
                else:
                    m['random_weight'] = 0.0

                m['vote_weight'] = vote_weight * recipe.WEIGHT_VOTE
                m['age_weight'] = age_weight * recipe.WEIGHT_AGE

                weight = (m['index_weight'] + m['vote_weight']
                          + m['age_weight'] + m['random_weight'])
                for genre, value in recipe.WEIGHT_GENRE_BIAS.items():
                    if genre.lower() in m['genres']:
                        weight *= value

                m['weight'] = weight
            else:
                m['vote_weight'] = 0.0
                m['age_weight'] = 0.0
                m['weight'] = index_weight
            item_list[i] = m

        item_list.sort(key = lambda m: m['weight'], reverse=True)

        for i, m in enumerate(item_list):
            if (i+1) < m['original_idx']:
                net = Colors.GREEN + u'↑'
            elif (i+1) > m['original_idx']:
                net = Colors.RED + u'↓'
            else:
                net = u' '
            net += str(abs(i + 1 - m['original_idx'])).rjust(3)
            print(u"{} {:>3}: trnd:{:>3}, w_trnd:{:0<5}; vote:{}, w_vote:{:0<5}; "
                "age:{:>4}, w_age:{:0<5}; w_rnd:{:0<5}; w_cmb:{:0<5}; {} "
                "{}{}".format(
                    net, i+1, m['original_idx'], round(m['index_weight'], 3),
                    m.get('tmdb_vote'), round(m['vote_weight'], 3), m.get('age'),
                    round(m['age_weight'], 3), round(m.get('random_weight', 0), 3),
                    round(m['weight'], 3), m['title'], m['year'], Colors.RESET))

        return item_list

    def _run(self):
        item_list = []
        item_ids = []
        force_imdb_id_match = False
        curyear = datetime.datetime.now().year

        def _movie_add_from_trakt_list(url):
            print(u"Retrieving the trakt list: {}".format(url))
            movie_data = self.trakt_core._handle_request('get', url)
            for m in movie_data:
                # Skip already added movies
                if m['movie']['ids']['imdb'] in item_ids:
                    continue
                # Skip old movies
                if self.recipe.MAX_AGE != 0 \
                        and (curyear - (self.recipe.MAX_AGE - 1)) > int(m['movie']['year']):
                    continue
                item_list.append({
                    'id': m['movie']['ids']['imdb'],
                    'tmdb_id': m['movie']['ids'].get('tmdb', ''),
                    'title': m['movie']['title'],
                    'year': m['movie']['year'],
                })
                item_ids.append(m['movie']['ids']['imdb'])
                if m['movie']['ids'].get('tmdb'):
                    item_ids.append('tmdb' + str(m['movie']['ids']['tmdb']))
                else:
                    force_imdb_id_match = True

        def _tv_add_from_trakt_list(url):
            print(u"Retrieving the trakt list: {}".format(url))
            show_data = self.trakt_core._handle_request('get', url)
            for m in show_data:
                # Skip already added shows
                if m['show']['ids']['imdb'] in item_ids:
                    continue
                # Skip old shows
                if self.recipe.MAX_AGE != 0 \
                        and (curyear - (self.recipe.MAX_AGE - 1)) > int(m['show']['year']):
                    continue
                item_list.append({
                    'id': m['show']['ids']['imdb'],
                    'tmdb_id': m['show']['ids'].get('tmdb', ''),
                    'tvdb_id': m['show']['ids'].get('tvdb', ''),
                    'title': m['show']['title'],
                    'year': m['show']['year'],
                })
                item_ids.append(m['show']['ids']['imdb'])
                if m['show']['ids'].get('tmdb'):
                    item_ids.append('tmdb' + str(m['show']['ids']['tmdb']))
                else:
                    force_imdb_id_match = True
                if m['show']['ids'].get('tvdb'):
                    item_ids.append('tvdb' + str(m['show']['ids']['tvdb']))
                else:
                    force_imdb_id_match = True

        # Get the trakt lists
        if self.library_type == 'movie':
            for url in self.recipe.SOURCE_LIST_URLS:
                _movie_add_from_trakt_list(url)
        else:
            for url in self.recipe.SOURCE_LIST_URLS:
                _tv_add_from_trakt_list(url)

        if self.recipe.WEIGHTED_SORTING:
            if config.TMDB_API_KEY:
                print(u"Getting data from TMDb to add weighted sorting...")
                item_list = weighted_sorting(item_list, self.recipe, self.library_type)
            else:
                print(u"Warning: TMDd API key is required for weighted sorting")

        # Get list of items from the Plex server
        print(u"Trying to match with items from the '{library}' library ".format(
            library=self.recipe.SOURCE_LIBRARY_NAME))
        try:
            source_library = self.plex.library.section(self.recipe.SOURCE_LIBRARY_NAME)
        except:
            print(u"The '{library}' library does not exist in Plex.".format(
                library=self.recipe.SOURCE_LIBRARY_NAME))
            print(u"Exiting script.")
            return 0

        # Create a list of matching items
        matching_items = []
        missing_items = []
        matching_total = 0
        nonmatching_idx = []

        for i, item in enumerate(item_list):
            match = False
            if self.recipe.MAX_COUNT > 0 and matching_total >= self.recipe.MAX_COUNT:
                nonmatching_idx.append(i)
                continue
            res = source_library.search(guid='imdb://' + str(item['id']))
            if not res and item.get('tmdb_id'):
                res = source_library.search(
                    guid='themoviedb://' + str(item['tmdb_id']))
            if not res and item.get('tvdb_id'):
                res = source_library.search(
                    guid='thetvdb://' + str(item['tvdb_id']))
            if not res:
                missing_items.append((i, item))
                nonmatching_idx.append(i)
                continue

            for r in res:
                imdb_id = None
                tmdb_id = None
                tvdb_id = None
                if r.guid != None and 'imdb://' in r.guid:
                    imdb_id = r.guid.split('imdb://')[1].split('?')[0]
                elif r.guid != None and 'themoviedb://' in r.guid:
                    tmdb_id = r.guid.split('themoviedb://')[1].split('?')[0]
                elif r.guid != None and 'thetvdb://' in r.guid:
                    tvdb_id = r.guid.split('thetvdb://')[1].split('?')[0].split('/')[0]

                if ((imdb_id and imdb_id == str(item['id']))
                        or (tmdb_id and tmdb_id == str(item['tmdb_id']))
                        or (tvdb_id and tvdb_id == str(item['tvdb_id']))):
                    if not match:
                        match = True
                        matching_total += 1
                    matching_items.append(r)

            if match:
                if self.recipe.SORT_TITLE_ABSOLUTE:
                    print(u"{} {} ({})".format(
                        i+1, item['title'], item['year']))
                else:
                    print(u"{} {} ({})".format(
                        matching_total, item['title'], item['year']))
            else:
                missing_items.append((i, item))
                nonmatching_idx.append(i)

        if not self.recipe.SORT_TITLE_ABSOLUTE:
            for i in reversed(nonmatching_idx):
                del item_list[i]

        # Create symlinks for all items in your library on the trakt watched
        print(u"Creating symlinks for {count} matching items in the "
              u"library...".format(count=matching_total))

        try:
            if not os.path.exists(self.recipe.NEW_LIBRARY_FOLDER):
                os.mkdir(self.recipe.NEW_LIBRARY_FOLDER)
        except:
            print(u"Unable to create the new library folder "
                  u"'{folder}'.".format(folder=self.recipe.NEW_LIBRARY_FOLDER))
            print(u"Exiting script.")
            return 0

        count = 0
        updated_paths = []
        new_items = []
        if self.library_type == 'movie':
            for movie in matching_items:
                for part in movie.iterParts():
                    old_path_file = part.file.encode('UTF-8')
                    old_path, file_name = os.path.split(old_path_file)

                    folder_name = ''
                    for f in self.recipe.SOURCE_LIBRARY_FOLDERS:
                        f = os.path.abspath(f).encode('utf8')
                        if old_path.lower().startswith(f.lower()):
                            folder_name = os.path.relpath(old_path, f)

                    if folder_name == '.':
                        new_path = os.path.join(self.recipe.NEW_LIBRARY_FOLDER.encode('utf8'), file_name)
                        dir = False
                    else:
                        new_path = os.path.join(self.recipe.NEW_LIBRARY_FOLDER.encode('utf8'), folder_name)
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
                            new_items.append(movie)
                            updated_paths.append(new_path)
                        except Exception as e:
                            print(u"Symlink failed for {path}: {e}".format(
                                path=new_path, e=e))
        else:
            for tv_show in matching_items:
                done = False
                if done:
                    continue
                for episode in tv_show.episodes():
                    if done:
                        break
                    for part in episode.iterParts():
                        if done:
                            break
                        old_path_file = part.file.encode('UTF-8')
                        old_path, file_name = os.path.split(old_path_file)
                        old_path = (
                            self.recipe.SOURCE_LIBRARY_FOLDERS[0]
                            + '/'
                            + old_path.replace(
                                self.recipe.SOURCE_LIBRARY_FOLDERS[0],
                                ''
                              ).strip('/').split('/')[0])

                        folder_name = ''
                        for f in self.recipe.SOURCE_LIBRARY_FOLDERS:
                            if old_path.lower().startswith(f.lower()):
                                folder_name = os.path.relpath(old_path, f)

                        new_path = os.path.join(self.recipe.NEW_LIBRARY_FOLDER, folder_name)
                        dir = True

                        if ((dir and not os.path.exists(new_path))
                                or (not dir and not os.path.isfile(new_path))):
                            try:
                                if os.name == 'nt':
                                    if dir:
                                        subprocess.call(['mklink', '/D', new_path, old_path], shell=True)
                                    else:
                                        subprocess.call(['mklink', new_path, old_path_file], shell=True)
                                else:
                                    if dir:
                                        os.symlink(old_path, new_path)
                                    else:
                                        os.symlink(old_path_file, new_path)
                                count += 1
                                new_items.append(tv_show)
                                updated_paths.append(new_path)
                                done = True
                            except Exception as e:
                                print(u"Symlink failed for {path}: {e}".format(path=new_path, e=e))

        print(u"Created symlinks for {count} new items:".format(count=count))
        for item in new_items:
            print(u"{title} ({year})".format(title=item.title, year=item.year))

        # Check if the new library exists in Plex
        print(u"Creating the '{}' library in Plex...".format(
            self.recipe.NEW_LIBRARY_NAME))
        try:
            new_library = self.plex.library.section(self.recipe.NEW_LIBRARY_NAME)
            new_library_key = new_library.key
            print(u"Library already exists in Plex. Scanning the library...")

            new_library.update()
        except:
            plexutils.create_new_library(self.recipe.NEW_LIBRARY_NAME, self.recipe.NEW_LIBRARY_FOLDER, self.library_type)
            new_library = self.plex.library.section(self.recipe.NEW_LIBRARY_NAME)
            new_library_key = new_library.key

        # Wait for metadata to finish downloading before continuing
        print(u"Waiting for metadata to finish downloading...")
        new_library = self.plex.library.section(self.recipe.NEW_LIBRARY_NAME)
        while new_library.refreshing:
            time.sleep(5)
            new_library = self.plex.library.section(self.recipe.NEW_LIBRARY_NAME)

        # Retrieve a list of items from the new library
        print(u"Retrieving a list of items from the '{library}' library in "
              u"Plex...".format(library=self.recipe.NEW_LIBRARY_NAME))
        all_new_items = new_library.all()

        # Create a dictionary of {imdb_id: item}
        imdb_map = {}
        for m in all_new_items:
            imdb_id = None
            tmdb_id = None
            tvdb_id = None
            if m.guid != None and 'imdb://' in m.guid:
                imdb_id = m.guid.split('imdb://')[1].split('?')[0]
            elif m.guid != None and 'themoviedb://' in m.guid:
                tmdb_id = m.guid.split('themoviedb://')[1].split('?')[0]
            elif m.guid != None and 'thetvdb://' in m.guid:
                tvdb_id = m.guid.split('thetvdb://')[1].split('?')[0].split('/')[0]
            else:
                imdb_id = None

            if imdb_id and str(imdb_id) in item_ids:
                imdb_map[imdb_id] = m
            elif tmdb_id and ('tmdb' + str(tmdb_id)) in item_ids:
                imdb_map['tmdb' + str(tmdb_id)] = m
            elif tvdb_id and ('tvdb' + str(tvdb_id)) in item_ids:
                imdb_map['tvdb' + str(tvdb_id)] = m
            elif force_imdb_id_match:
                # Only IMDB ID found for some items
                if tmdb_id:
                    imdb_id = tmdb.get_imdb_id(tmdb_id)
                elif tvdb_id:
                    imdb_id = tvdb.get_imdb_id(tvdb_id)
                if imdb_id and str(imdb_id) in item_ids:
                    imdb_map[imdb_id] = m
                else:
                    imdb_map[m.ratingKey] = m
            else:
                imdb_map[m.ratingKey] = m

        # Modify the sort titles
        print(u"Setting the sort titles for the '{}' library...".format(
            self.recipe.NEW_LIBRARY_NAME))
        if self.recipe.SORT_TITLE_ABSOLUTE:
            for i, m in enumerate(item_list):
                item = imdb_map.pop(m['id'], None)
                if not item:
                    item = imdb_map.pop('tmdb' + str(m.get('tmdb_id', '')), None)
                if not item:
                    item = imdb_map.pop('tvdb' + str(m.get('tvdb_id', '')), None)
                if item:
                    plexutils.add_sort_title(new_library_key, item.ratingKey, i+1, m['title'], self.library_type)
        else:
            i = 0
            for m in item_list:
                item = imdb_map.pop(m['id'], None)
                if not item:
                    item = imdb_map.pop('tmdb' + str(m.get('tmdb_id', '')), None)
                if not item:
                    item = imdb_map.pop('tvdb' + str(m.get('tvdb_id', '')), None)
                if item:
                    i += 1
                    plexutils.add_sort_title(new_library_key, item.ratingKey, i, m['title'], self.library_type)

        if self.recipe.REMOVE_FROM_LIBRARY:
            # Remove items from the new library which no longer qualify
            print(u"Removing symlinks for items which no longer qualify ".format(
                library=self.recipe.NEW_LIBRARY_NAME))
            count = 0
            updated_paths = []
            deleted_items = []
            if self.library_type == 'movie':
                for movie in imdb_map.values():
                    for part in movie.iterParts():
                        old_path_file = part.file.encode('UTF-8')
                        old_path, file_name = os.path.split(old_path_file)

                        folder_name = os.path.relpath(old_path, self.recipe.NEW_LIBRARY_FOLDER)

                        if folder_name == '.':
                            new_path = os.path.join(self.recipe.NEW_LIBRARY_FOLDER, file_name)
                            dir = False
                        else:
                            new_path = os.path.join(self.recipe.NEW_LIBRARY_FOLDER, folder_name)
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
                                deleted_items.append(movie)
                                updated_paths.append(new_path)
                            except Exception as e:
                                print(u"Remove symlink failed for {path}: {e}".format(
                                    path=new_path, e=e))
            else:
                for tv_show in imdb_map.values():
                    done = False
                    if done:
                        continue
                    for episode in tv_show.episodes():
                        if done:
                            break
                        for part in episode.iterParts():
                            if done:
                                break
                            old_path_file = part.file.encode('UTF-8')
                            old_path, file_name = os.path.split(old_path_file)
                            old_path =  TV_LIBRARY_FOLDERS[0] + '/' + old_path.replace(TV_LIBRARY_FOLDERS[0], '').strip('/').split('/')[0]

                            folder_name = ''
                            for f in TV_LIBRARY_FOLDERS:
                                if old_path.lower().startswith(f.lower()):
                                    folder_name = os.path.relpath(old_path, f)

                            new_path = os.path.join(self.recipe.NEW_LIBRARY_FOLDER, folder_name)
                            dir = True

                            if (dir and os.path.exists(new_path)) or (not dir and os.path.isfile(new_path)):
                                try:
                                    if os.name == 'nt':
                                        if dir:
                                            os.rmdir(new_path)
                                        else:
                                            os.remove(new_path)
                                    else:
                                        os.unlink(new_path)
                                    count += 1
                                    deleted_items.append(tv_show)
                                    updated_paths.append(new_path)
                                except Exception as e:
                                    print(u"Remove symlink failed for {path}: {e}".format(path=new_path, e=e))

            print(u"Removed symlinks for {count} items.".format(count=count))
            for item in deleted_items:
                print(u"{title} ({year})".format(title=item.title, year=item.year))

            # Scan the library to clean up the deleted items
            print(u"Scanning the '{library}' library...".format(
                library=self.recipe.NEW_LIBRARY_NAME))
            new_library.update()
            time.sleep(10)
            new_library = self.plex.library.section(self.recipe.NEW_LIBRARY_NAME)
            while new_library.refreshing:
                time.sleep(5)
                new_library = self.plex.library.section(self.recipe.NEW_LIBRARY_NAME)
            new_library.emptyTrash()
            all_new_items = new_library.all()
        else:
            while imdb_map:
                imdb_id, item = imdb_map.popitem()
                i += 1
                plexutils.add_sort_title(new_library_key, item.ratingKey, i, item.title, self.library_type)

        return missing_items, len(all_new_items)

    def _run_sort_only(self):
        item_list = []
        item_ids = []
        force_imdb_id_match = False
        curyear = datetime.datetime.now().year

        def _movie_add_from_trakt_list(url):
            print(u"Retrieving the trakt list: {}".format(url))
            movie_data = self.trakt_core._handle_request('get', url)
            for m in movie_data:
                # Skip already added movies
                if m['movie']['ids']['imdb'] in item_ids:
                    continue
                # Skip old movies
                if self.recipe.MAX_AGE != 0 \
                        and (curyear - (self.recipe.MAX_AGE - 1)) > int(m['movie']['year']):
                    continue
                item_list.append({
                    'id': m['movie']['ids']['imdb'],
                    'tmdb_id': m['movie']['ids'].get('tmdb', ''),
                    'title': m['movie']['title'],
                    'year': m['movie']['year'],
                })
                item_ids.append(m['movie']['ids']['imdb'])
                if m['movie']['ids'].get('tmdb'):
                    item_ids.append('tmdb' + str(m['movie']['ids']['tmdb']))
                else:
                    force_imdb_id_match = True

        def _tv_add_from_trakt_list(url):
            print(u"Retrieving the trakt list: {}".format(url))
            show_data = self.trakt_core._handle_request('get', url)
            for m in show_data:
                # Skip already added shows
                if m['show']['ids']['imdb'] in item_ids:
                    continue
                # Skip old shows
                if self.recipe.MAX_AGE != 0 \
                        and (curyear - (self.recipe.MAX_AGE - 1)) > int(m['show']['year']):
                    continue
                item_list.append({
                    'id': m['show']['ids']['imdb'],
                    'tmdb_id': m['show']['ids'].get('tmdb', ''),
                    'tvdb_id': m['show']['ids'].get('tvdb', ''),
                    'title': m['show']['title'],
                    'year': m['show']['year'],
                })
                item_ids.append(m['show']['ids']['imdb'])
                if m['show']['ids'].get('tmdb'):
                    item_ids.append('tmdb' + str(m['show']['ids']['tmdb']))
                else:
                    force_imdb_id_match = True
                if m['show']['ids'].get('tvdb'):
                    item_ids.append('tvdb' + str(m['show']['ids']['tvdb']))
                else:
                    force_imdb_id_match = True

        # Get the trakt lists
        if self.library_type == 'movie':
            for url in self.recipe.SOURCE_LIST_URLS:
                _movie_add_from_trakt_list(url)
        else:
            for url in self.recipe.SOURCE_LIST_URLS:
                _tv_add_from_trakt_list(url)

        if self.recipe.WEIGHTED_SORTING:
            if config.TMDB_API_KEY:
                print(u"Getting data from TMDb to add weighted sorting...")
                item_list = weighted_sorting(item_list, self.recipe, self.library_type)
            else:
                print(u"Warning: TMDd API key is required for weighted sorting")

        try:
            new_library = self.plex.library.section(self.recipe.NEW_LIBRARY_NAME)
            new_library_key = new_library.key
        except:
            raise Exception("Library '{library}' does not exist".format(
                library=self.recipe.NEW_LIBRARY_NAME))

        new_library.update()
        # Wait for metadata to finish downloading before continuing
        print(u"Waiting for metadata to finish downloading...")
        new_library = self.plex.library.section(self.recipe.NEW_LIBRARY_NAME)
        while new_library.refreshing:
            time.sleep(5)
            new_library = self.plex.library.section(self.recipe.NEW_LIBRARY_NAME)

        # Retrieve a list of items from the new library
        print(u"Retrieving a list of items from the '{library}' library in "
              u"Plex...".format(library=self.recipe.NEW_LIBRARY_NAME))
        all_new_items = new_library.all()

        # Create a dictionary of {imdb_id: item}
        imdb_map = {}
        for m in all_new_items:
            imdb_id = None
            tmdb_id = None
            tvdb_id = None
            if m.guid != None and 'imdb://' in m.guid:
                imdb_id = m.guid.split('imdb://')[1].split('?')[0]
            elif m.guid != None and 'themoviedb://' in m.guid:
                tmdb_id = m.guid.split('themoviedb://')[1].split('?')[0]
            elif m.guid != None and 'thetvdb://' in m.guid:
                tvdb_id = m.guid.split('thetvdb://')[1].split('?')[0].split('/')[0]
            else:
                imdb_id = None

            if imdb_id and str(imdb_id) in item_ids:
                imdb_map[imdb_id] = m
            elif tmdb_id and ('tmdb' + str(tmdb_id)) in item_ids:
                imdb_map['tmdb' + str(tmdb_id)] = m
            elif tvdb_id and ('tvdb' + str(tvdb_id)) in item_ids:
                imdb_map['tvdb' + str(tvdb_id)] = m
            elif force_imdb_id_match:
                # Only IMDB ID found for some items
                if tmdb_id:
                    imdb_id = tmdb.get_imdb_id(tmdb_id)
                elif tvdb_id:
                    imdb_id = tvdb.get_imdb_id(tvdb_id)
                if imdb_id and str(imdb_id) in item_ids:
                    imdb_map[imdb_id] = m
                else:
                    imdb_map[m.ratingKey] = m

        # Modify the sort titles
        print(u"Setting the sort titles for the '{}' library...".format(
            self.recipe.NEW_LIBRARY_NAME))
        if self.recipe.SORT_TITLE_ABSOLUTE:
            for i, m in enumerate(item_list):
                item = imdb_map.pop(m['id'], None)
                if not item:
                    item = imdb_map.pop('tmdb' + str(m.get('tmdb_id', '')), None)
                if not item:
                    item = imdb_map.pop('tvdb' + str(m.get('tvdb_id', '')), None)
                if item:
                    plexutils.add_sort_title(new_library_key, item.ratingKey, i+1, m['title'], self.library_type)
        else:
            i = 0
            for m in item_list:
                item = imdb_map.pop(m['id'], None)
                if not item:
                    item = imdb_map.pop('tmdb' + str(m.get('tmdb_id', '')), None)
                if not item:
                    item = imdb_map.pop('tvdb' + str(m.get('tvdb_id', '')), None)
                if item:
                    i += 1
                    plexutils.add_sort_title(new_library_key, item.ratingKey, i, m['title'], self.library_type)
            while imdb_map:
                imdb_id, item = imdb_map.popitem()
                i += 1
                plexutils.add_sort_title(new_library_key, item.ratingKey, i, item.title, self.library_type)

        return len(all_new_items)

    def run(self, sort_only=False):
        if sort_only:
            print(u"Running the recipe '{}', sorting only".format(
                self.recipe_name))
            list_count = self._run_sort_only()
            print(u"Number of items in the new library: {count}".format(
                count=list_count))
        else:
            print(u"Running the recipe '{}'".format(self.recipe_name))
            missing_items, list_count = self._run()
            print(u"Number of items in the new library: {count}".format(
                count=list_count))
            print(u"Number of missing items: {count}".format(
                count=len(missing_items)))
            for idx, item in missing_items:
                print(u"{idx}\t{release}\t{imdb_id}\t{title} ({year})".format(
                    idx=idx+1, release=item.get('release_date', ''),
                    imdb_id=item['id'], title=item['title'], year=item['year']))

        print(u"Done!")

