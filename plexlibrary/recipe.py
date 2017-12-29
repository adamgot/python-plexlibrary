# -*- coding: utf-8 -*-
"""recipe
"""

import datetime
import errno
import os
import random
import subprocess
import sys
import time

import plexutils
import tmdb
import traktutils
import tvdb
from config import ConfigParser
from recipes import RecipeParser
from utils import Colors


class Recipe(object):
    plex = None
    trakt = None
    tmdb = None
    tvdb = None

    def __init__(self, recipe_name, sort_only=False, config_file=None):
        self.recipe_name = recipe_name

        self.config = ConfigParser(config_file)
        self.recipe = RecipeParser(recipe_name)

        if self.recipe['library_type'].lower().startswith('movie'):
            self.library_type = 'movie'
        elif self.recipe['library_type'].lower().startswith('tv'):
            self.library_type = 'tv'
        else:
            raise Exception("Library type should be 'movie' or 'tv'")

        # TODO: Support multiple libraries
        self.source_library_config = self.recipe['source_libraries'][0]

        self.plex = plexutils.Plex(self.config['plex']['baseurl'],
                                   self.config['plex']['token'])

        if self.config['trakt']['username']:
            self.trakt = traktutils.Trakt(
                self.config['trakt']['username'],
                client_id=self.config['trakt']['client_id'],
                client_secret=self.config['trakt']['client_secret'])

        if self.config['tmdb']['api_key']:
            self.tmdb = tmdb.TMDb(
                self.config['tmdb']['api_key'],
                cache_file=self.config['tmdb']['cache_file'])

        if self.config['tvdb']['username']:
            self.tvdb = tvdb.TheTVDB(self.config['tvdb']['username'],
                                     self.config['tvdb']['api_key'],
                                     self.config['tvdb']['user_key'])

    def _run(self):
        item_list = []  # TODO Replace with dict, scrap item_ids?
        item_ids = []
        force_imdb_id_match = False

        # Get the trakt lists
        for url in self.recipe['source_list_urls']:
            if 'api.trakt.tv' in url:
                (item_list, item_ids) = self.trakt.add_items(
                    self.library_type, url, item_list, item_ids,
                    self.recipe['new_library']['max_age'] or 0)
            else:
                raise Exception("Unsupported source list: {url}".format(
                    url=url))

        if self.recipe['weighted_sorting']['enabled']:
            if self.config['tmdb']['api_key']:
                print(u"Getting data from TMDb to add weighted sorting...")
                item_list = self.weighted_sorting(item_list)
            else:
                print(u"Warning: TMDd API key is required "
                      u"for weighted sorting")

        # Get list of items from the Plex server
        print(u"Trying to match with items from the '{}' library ".format(
            self.source_library_config['name']))
        try:
            source_library = self.plex.server.library.section(
                self.source_library_config['name'])
        except:
            raise Exception("The '{library}' library does not exist".format(
                library=self.source_library_config['name']))

        # FIXME: Hack until a new plexapi version is released. 3.0.4?
        if 'guid' not in source_library.ALLOWED_FILTERS:
            source_library.ALLOWED_FILTERS += ('guid',)

        # Create a list of matching items
        matching_items = []
        missing_items = []
        matching_total = 0
        nonmatching_idx = []
        max_count = self.recipe['new_library']['max_count']

        for i, item in enumerate(item_list):
            match = False
            if max_count > 0 and matching_total >= max_count:
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
                if r.guid is not None and 'imdb://' in r.guid:
                    imdb_id = r.guid.split('imdb://')[1].split('?')[0]
                elif r.guid is not None and 'themoviedb://' in r.guid:
                    tmdb_id = r.guid.split('themoviedb://')[1].split('?')[0]
                elif r.guid is not None and 'thetvdb://' in r.guid:
                    tvdb_id = (r.guid.split('thetvdb://')[1]
                               .split('?')[0]
                               .split('/')[0])

                if ((imdb_id and imdb_id == str(item['id']))
                        or (tmdb_id and tmdb_id == str(item['tmdb_id']))
                        or (tvdb_id and tvdb_id == str(item['tvdb_id']))):
                    if not match:
                        match = True
                        matching_total += 1
                    matching_items.append(r)

            if match:
                if self.recipe['new_library']['sort_title']['absolute']:
                    print(u"{} {} ({})".format(
                        i+1, item['title'], item['year']))
                else:
                    print(u"{} {} ({})".format(
                        matching_total, item['title'], item['year']))
            else:
                missing_items.append((i, item))
                nonmatching_idx.append(i)

        if not self.recipe['new_library']['sort_title']['absolute']:
            for i in reversed(nonmatching_idx):
                del item_list[i]

        # Create symlinks for all items in your library on the trakt watched
        print(u"Creating symlinks for {count} matching items in the "
              u"library...".format(count=matching_total))

        try:
            if not os.path.exists(self.recipe['new_library']['folder']):
                os.mkdir(self.recipe['new_library']['folder'])
        except:
            print(u"Unable to create the new library folder "
                  u"'{folder}'.".format(
                      folder=self.recipe['new_library']['folder']))
            print(u"Exiting script.")
            return 0

        count = 0
        updated_paths = []
        new_items = []
        if self.library_type == 'movie':
            for movie in matching_items:
                for part in movie.iterParts():
                    old_path_file = part.file
                    old_path, file_name = os.path.split(old_path_file)

                    folder_name = ''
                    for f in self.source_library_config['folders']:
                        f = os.path.abspath(f)
                        if old_path.lower().startswith(f.lower()):
                            folder_name = os.path.relpath(old_path, f)

                    if folder_name == '.':
                        new_path = os.path.join(
                            self.recipe['new_library']['folder'], file_name)
                        dir = False
                    else:
                        new_path = os.path.join(
                            self.recipe['new_library']['folder'], folder_name)
                        dir = True
                        parent_path = os.path.dirname(
                            os.path.abspath(new_path))
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
                        if (os.path.exists(new_path) and not
                                os.listdir(new_path)):
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
                                                    old_path_file],
                                                    shell=True)
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
                        old_path_file = part.file
                        old_path, file_name = os.path.split(old_path_file)

                        folder_name = ''
                        for f in self.source_library_config['folders']:
                            if old_path.lower().startswith(f.lower()):
                                old_path = os.path.join(f, old_path.replace(
                                    f, '').strip(os.sep).split(os.sep)[0])
                                folder_name = os.path.relpath(old_path, f)

                        new_path = os.path.join(
                            self.recipe['new_library']['folder'], folder_name)

                        if not os.path.exists(new_path):
                            try:
                                if os.name == 'nt':
                                    subprocess.call(['mklink', '/D', new_path,
                                                     old_path], shell=True)
                                else:
                                    os.symlink(old_path, new_path)
                                count += 1
                                new_items.append(tv_show)
                                updated_paths.append(new_path)
                                done = True
                                break
                            except Exception as e:
                                print(u"Symlink failed for {path}: {e}".format(
                                    path=new_path, e=e))
                        else:
                            done = True
                            break

        print(u"Created symlinks for {count} new items:".format(count=count))
        for item in new_items:
            print(u"{title} ({year})".format(title=item.title, year=item.year))

        # Check if the new library exists in Plex
        print(u"Creating the '{}' library in Plex...".format(
            self.recipe['new_library']['name']))
        try:
            new_library = self.plex.server.library.section(
                self.recipe['new_library']['name'])
            print(u"Library already exists in Plex. Scanning the library...")

            new_library.update()
        except:
            self.plex.create_new_library(
                self.recipe['new_library']['name'],
                self.recipe['new_library']['folder'],
                self.library_type)
            new_library = self.plex.server.library.section(
                self.recipe['new_library']['name'])

        # Wait for metadata to finish downloading before continuing
        print(u"Waiting for metadata to finish downloading...")
        new_library = self.plex.server.library.section(
            self.recipe['new_library']['name'])
        while new_library.refreshing:
            time.sleep(5)
            new_library = self.plex.server.library.section(
                self.recipe['new_library']['name'])

        # Retrieve a list of items from the new library
        print(u"Retrieving a list of items from the '{library}' library in "
              u"Plex...".format(library=self.recipe['new_library']['name']))
        all_new_items = new_library.all()

        # Create a dictionary of {imdb_id: item}
        imdb_map = {}
        for m in all_new_items:
            imdb_id = None
            tmdb_id = None
            tvdb_id = None
            if m.guid is not None and 'imdb://' in m.guid:
                imdb_id = m.guid.split('imdb://')[1].split('?')[0]
            elif m.guid is not None and 'themoviedb://' in m.guid:
                tmdb_id = m.guid.split('themoviedb://')[1].split('?')[0]
            elif m.guid is not None and 'thetvdb://' in m.guid:
                tvdb_id = (m.guid.split('thetvdb://')[1]
                           .split('?')[0]
                           .split('/')[0])
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
                    imdb_id = self.tmdb.get_imdb_id(tmdb_id)
                elif tvdb_id:
                    imdb_id = self.tvdb.get_imdb_id(tvdb_id)
                if imdb_id and str(imdb_id) in item_ids:
                    imdb_map[imdb_id] = m
                else:
                    imdb_map[m.ratingKey] = m
            else:
                imdb_map[m.ratingKey] = m

        # Modify the sort titles
        if self.recipe['new_library']['sort']:
            print(u"Setting the sort titles for the '{}' library...".format(
                self.recipe['new_library']['name']))
        if self.recipe['new_library']['sort_title']['absolute']:
            for i, m in enumerate(item_list):
                item = imdb_map.pop(m['id'], None)
                if not item:
                    item = imdb_map.pop('tmdb' + str(m.get('tmdb_id', '')),
                                        None)
                if not item:
                    item = imdb_map.pop('tvdb' + str(m.get('tvdb_id', '')),
                                        None)
                if item and self.recipe['new_library']['sort']:
                    self.plex.set_sort_title(
                        new_library.key, item.ratingKey, i+1, m['title'],
                        self.library_type,
                        self.recipe['new_library']['sort_title']['format'],
                        self.recipe['new_library']['sort_title']['visible']
                    )
        else:
            i = 0
            for m in item_list:
                item = imdb_map.pop(m['id'], None)
                if not item:
                    item = imdb_map.pop('tmdb' + str(m.get('tmdb_id', '')),
                                        None)
                if not item:
                    item = imdb_map.pop('tvdb' + str(m.get('tvdb_id', '')),
                                        None)
                if item and self.recipe['new_library']['sort']:
                    i += 1
                    self.plex.set_sort_title(
                        new_library.key, item.ratingKey, i, m['title'],
                        self.library_type,
                        self.recipe['new_library']['sort_title']['format'],
                        self.recipe['new_library']['sort_title']['visible']
                    )

        if self.recipe['new_library']['remove_from_library']:
            # Remove items from the new library which no longer qualify
            print(u"Removing symlinks for items "
                  "which no longer qualify ".format(
                    library=self.recipe['new_library']['name']))
            count = 0
            updated_paths = []
            deleted_items = []
            if self.library_type == 'movie':
                for movie in imdb_map.values():
                    for part in movie.iterParts():
                        old_path_file = part.file
                        old_path, file_name = os.path.split(old_path_file)

                        folder_name = os.path.relpath(
                            old_path, self.recipe['new_library']['folder'])

                        if folder_name == '.':
                            new_path = os.path.join(
                                self.recipe['new_library']['folder'],
                                file_name)
                            dir = False
                        else:
                            new_path = os.path.join(
                                self.recipe['new_library']['folder'],
                                folder_name)
                            dir = True

                        if (dir and os.path.exists(new_path)) or \
                                (not dir and os.path.isfile(new_path)):
                            try:
                                if os.name == 'nt':
                                    # Python 3.2+ only
                                    if sys.version_info < (3, 2):
                                        assert os.path.islink(new_path)
                                    if dir:
                                        os.rmdir(new_path)
                                    else:
                                        os.remove(new_path)
                                else:
                                    assert os.path.islink(new_path)
                                    os.unlink(new_path)
                                count += 1
                                deleted_items.append(movie)
                                updated_paths.append(new_path)
                            except Exception as e:
                                print(u"Remove symlink failed for "
                                      "{path}: {e}".format(path=new_path,
                                                           e=e))
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
                            old_path_file = part.file
                            old_path, file_name = os.path.split(old_path_file)

                            folder_name = ''
                            new_library_folder = \
                                self.recipe['new_library']['folder']
                            old_path = os.path.join(
                                new_library_folder,
                                old_path.replace(new_library_folder, '').strip(
                                    os.sep).split(os.sep)[0])
                            folder_name = os.path.relpath(old_path,
                                                          new_library_folder)

                            new_path = os.path.join(
                                self.recipe['new_library']['folder'],
                                folder_name)
                            if os.path.exists(new_path):
                                try:
                                    if os.name == 'nt':
                                        # Python 3.2+ only
                                        if sys.version_info < (3, 2):
                                            assert os.path.islink(new_path)
                                        os.rmdir(new_path)
                                    else:
                                        assert os.path.islink(new_path)
                                        os.unlink(new_path)
                                    count += 1
                                    deleted_items.append(tv_show)
                                    updated_paths.append(new_path)
                                    done = True
                                    break
                                except Exception as e:
                                    print(u"Remove symlink failed for "
                                          "{path}: {e}".format(path=new_path,
                                                               e=e))
                            else:
                                done = True
                                break

            print(u"Removed symlinks for {count} items.".format(count=count))
            for item in deleted_items:
                print(u"{title} ({year})".format(title=item.title,
                                                 year=item.year))

            # Scan the library to clean up the deleted items
            print(u"Scanning the '{library}' library...".format(
                library=self.recipe['new_library']['name']))
            new_library.update()
            time.sleep(10)
            new_library = self.plex.server.library.section(
                self.recipe['new_library']['name'])
            while new_library.refreshing:
                time.sleep(5)
                new_library = self.plex.server.library.section(
                    self.recipe['new_library']['name'])
            new_library.emptyTrash()
            all_new_items = new_library.all()
        else:
            while imdb_map:
                imdb_id, item = imdb_map.popitem()
                i += 1
                self.plex.set_sort_title(
                    new_library.key, item.ratingKey, i, item.title,
                    self.library_type,
                    self.recipe['new_library']['sort_title']['format'],
                    self.recipe['new_library']['sort_title']['visible'])

        return missing_items, len(all_new_items)

    def _run_sort_only(self):
        item_list = []
        item_ids = []
        force_imdb_id_match = False

        # Get the trakt lists
        for url in self.recipe['source_list_urls']:
            if 'api.trakt.tv' in url:
                (item_list, item_ids) = self.trakt.add_items(
                    self.library_type, url, item_list, item_ids,
                    self.recipe['new_library']['max_age'] or 0)
            else:
                raise Exception("Unsupported source list: {url}".format(
                    url=url))

        if self.recipe['weighted_sorting']['enabled']:
            if self.config['tmdb']['api_key']:
                print(u"Getting data from TMDb to add weighted sorting...")
                item_list = self.weighted_sorting(item_list)
            else:
                print(u"Warning: TMDd API key is required "
                      "for weighted sorting")

        try:
            new_library = self.plex.server.library.section(
                self.recipe['new_library']['name'])
        except:
            raise Exception("Library '{library}' does not exist".format(
                library=self.recipe['new_library']['name']))

        new_library.update()
        # Wait for metadata to finish downloading before continuing
        print(u"Waiting for metadata to finish downloading...")
        new_library = self.plex.server.library.section(
            self.recipe['new_library']['name'])
        while new_library.refreshing:
            time.sleep(5)
            new_library = self.plex.server.library.section(
                self.recipe['new_library']['name'])

        # Retrieve a list of items from the new library
        print(u"Retrieving a list of items from the '{library}' library in "
              u"Plex...".format(library=self.recipe['new_library']['name']))
        all_new_items = new_library.all()

        # Create a dictionary of {imdb_id: item}
        imdb_map = {}
        for m in all_new_items:
            imdb_id = None
            tmdb_id = None
            tvdb_id = None
            if m.guid is not None and 'imdb://' in m.guid:
                imdb_id = m.guid.split('imdb://')[1].split('?')[0]
            elif m.guid is not None and 'themoviedb://' in m.guid:
                tmdb_id = m.guid.split('themoviedb://')[1].split('?')[0]
            elif m.guid is not None and 'thetvdb://' in m.guid:
                tvdb_id = (m.guid.split('thetvdb://')[1]
                           .split('?')[0]
                           .split('/')[0])
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
                    imdb_id = self.tmdb.get_imdb_id(tmdb_id)
                elif tvdb_id:
                    imdb_id = self.tvdb.get_imdb_id(tvdb_id)
                if imdb_id and str(imdb_id) in item_ids:
                    imdb_map[imdb_id] = m
                else:
                    imdb_map[m.ratingKey] = m
            else:
                imdb_map[m.ratingKey] = m

        # Modify the sort titles
        print(u"Setting the sort titles for the '{}' library...".format(
            self.recipe['new_library']['name']))
        if self.recipe['new_library']['sort_title']['absolute']:
            for i, m in enumerate(item_list):
                item = imdb_map.pop(m['id'], None)
                if not item:
                    item = imdb_map.pop('tmdb' + str(m.get('tmdb_id', '')),
                                        None)
                if not item:
                    item = imdb_map.pop('tvdb' + str(m.get('tvdb_id', '')),
                                        None)
                if item:
                    self.plex.set_sort_title(
                        new_library.key, item.ratingKey, i+1, m['title'],
                        self.library_type,
                        self.recipe['new_library']['sort_title']['format'],
                        self.recipe['new_library']['sort_title']['visible'])
        else:
            i = 0
            for m in item_list:
                item = imdb_map.pop(m['id'], None)
                if not item:
                    item = imdb_map.pop('tmdb' + str(m.get('tmdb_id', '')),
                                        None)
                if not item:
                    item = imdb_map.pop('tvdb' + str(m.get('tvdb_id', '')),
                                        None)
                if item:
                    i += 1
                    self.plex.set_sort_title(
                        new_library.key, item.ratingKey, i, m['title'],
                        self.library_type,
                        self.recipe['new_library']['sort_title']['format'],
                        self.recipe['new_library']['sort_title']['visible'])
            while imdb_map:
                imdb_id, item = imdb_map.popitem()
                i += 1
                self.plex.set_sort_title(
                    new_library.key, item.ratingKey, i, item.title,
                    self.library_type,
                    self.recipe['new_library']['sort_title']['format'],
                    self.recipe['new_library']['sort_title']['visible'])

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
                    imdb_id=item['id'], title=item['title'],
                    year=item['year']))

    def weighted_sorting(self, item_list):
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
            if self.library_type == 'movie':
                # Everything younger than this will get 1
                min_days = 180
                # Everything older than this will get 0
                max_days = (float(self.recipe['new_library']['max_age'])
                            / 4.0 * 365.25 or 360)
            else:
                min_days = 14
                max_days = (float(self.recipe['new_library']['max_age'])
                            / 4.0 * 365.25 or 180)
            if days <= min_days:
                return 1
            elif days >= max_days:
                return 0
            else:
                return 1 - (days - min_days) / (max_days - min_days)

        total_items = len(item_list)

        weights = self.recipe['weighted_sorting']['weights']

        # TMDB details
        today = datetime.date.today()
        total_tmdb_vote = 0.0
        tmdb_votes = []
        for i, m in enumerate(item_list):
            m['original_idx'] = i + 1
            details = self.tmdb.get_details(m['tmdb_id'], self.library_type)
            if not details:
                print(u"Warning: No TMDb data for {}".format(m['title']))
                continue
            m['tmdb_popularity'] = float(details['popularity'])
            m['tmdb_vote'] = float(details['vote_average'])
            m['tmdb_vote_count'] = int(details['vote_count'])
            if self.library_type == 'movie':
                if self.recipe['weighted_sorting']['better_release_date']:
                    m['release_date'] = _get_non_theatrical_release(
                        details['release_dates']) or \
                        datetime.datetime.strptime(details['release_date'],
                                                   '%Y-%m-%d').date()
                else:
                    m['release_date'] = datetime.datetime.strptime(
                        details['release_date'], '%Y-%m-%d').date()
                item_age_td = today - m['release_date']
            elif self.library_type == 'tv':
                m['last_air_date'] = datetime.datetime.strptime(
                    details['last_air_date'], '%Y-%m-%d').date()
                item_age_td = today - m['last_air_date']
            m['genres'] = [g['name'].lower() for g in details['genres']]
            m['age'] = item_age_td.days
            if (self.library_type == 'tv' or m['tmdb_vote_count'] > 150 or
                    m['age'] > 50):
                tmdb_votes.append(m['tmdb_vote'])
            total_tmdb_vote += m['tmdb_vote']
            item_list[i] = m

        tmdb_votes.sort()

        for i, m in enumerate(item_list):
            # Distribute all weights evenly from 0 to 1 (times global factor)
            # More weight means it'll go higher in the final list
            index_weight = float(total_items - i) / float(total_items)
            m['index_weight'] = index_weight * weights['index']
            if m.get('tmdb_popularity'):
                if (self.library_type == 'tv' or
                        m.get('tmdb_vote_count') > 150 or m['age'] > 50):
                    vote_weight = ((tmdb_votes.index(m['tmdb_vote']) + 1)
                                   / float(len(tmdb_votes)))
                else:
                    # Assume below average rating for new/less voted items
                    vote_weight = 0.25
                age_weight = _get_age_weight(float(m['age']))

                if weights.get('random'):
                    random_weight = random.random()
                    m['random_weight'] = random_weight * weights['random']
                else:
                    m['random_weight'] = 0.0

                m['vote_weight'] = vote_weight * weights['vote']
                m['age_weight'] = age_weight * weights['age']

                weight = (m['index_weight'] + m['vote_weight']
                          + m['age_weight'] + m['random_weight'])
                for genre, value in weights['genre_bias'].items():
                    if genre.lower() in m['genres']:
                        weight *= value

                m['weight'] = weight
            else:
                m['vote_weight'] = 0.0
                m['age_weight'] = 0.0
                m['weight'] = index_weight
            item_list[i] = m

        item_list.sort(key=lambda m: m['weight'], reverse=True)

        for i, m in enumerate(item_list):
            if (i+1) < m['original_idx']:
                net = Colors.GREEN + u'↑'
            elif (i+1) > m['original_idx']:
                net = Colors.RED + u'↓'
            else:
                net = u' '
            net += str(abs(i + 1 - m['original_idx'])).rjust(3)
            try:
                # TODO
                print(u"{} {:>3}: trnd:{:>3}, w_trnd:{:0<5}; vote:{}, "
                      "w_vote:{:0<5}; age:{:>4}, w_age:{:0<5}; w_rnd:{:0<5}; "
                      "w_cmb:{:0<5}; {} {}{}"
                      .format(net, i+1, m['original_idx'],
                              round(m['index_weight'], 3),
                              m.get('tmdb_vote', 0.0),
                              round(m['vote_weight'], 3), m.get('age', 0),
                              round(m['age_weight'], 3),
                              round(m.get('random_weight', 0), 3),
                              round(m['weight'], 3), str(m['title']),
                              str(m['year']), Colors.RESET))
            except UnicodeEncodeError:
                pass

        return item_list
