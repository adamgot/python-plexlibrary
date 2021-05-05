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
import logs

import plexapi

import plexutils
import tmdb
import traktutils
import imdbutils
import tvdb
from config import ConfigParser
from recipes import RecipeParser
from utils import Colors, add_years


class Recipe(object):
    plex = None
    trakt = None
    tmdb = None
    tvdb = None

    def __init__(self, recipe_name, sort_only=False, config_file=None, use_playlists=False):
        self.recipe_name = recipe_name
        self.use_playlists = use_playlists

        self.config = ConfigParser(config_file)
        self.recipe = RecipeParser(recipe_name)

        if not self.config.validate():
            raise Exception("Error(s) in config")

        if not self.recipe.validate(use_playlists=use_playlists):
            raise Exception("Error(s) in recipe")

        if self.recipe['library_type'].lower().startswith('movie'):
            self.library_type = 'movie'
        elif self.recipe['library_type'].lower().startswith('tv'):
            self.library_type = 'tv'
        else:
            raise Exception("Library type should be 'movie' or 'tv'")

        self.source_library_config = self.recipe['source_libraries']

        self.plex = plexutils.Plex(self.config['plex']['baseurl'],
                                   self.config['plex']['token'])

        if self.config['trakt']['username']:
            self.trakt = traktutils.Trakt(
                self.config['trakt']['username'],
                client_id=self.config['trakt']['client_id'],
                client_secret=self.config['trakt']['client_secret'],
                oauth_token=self.config['trakt'].get('oauth_token', ''),
                oauth=self.recipe.get('trakt_oauth', False),
                config=self.config)
            if self.trakt.oauth_token:
                self.config['trakt']['oauth_token'] = self.trakt.oauth_token

        if self.config['tmdb']['api_key']:
            self.tmdb = tmdb.TMDb(
                self.config['tmdb']['api_key'],
                cache_file=self.config['tmdb']['cache_file'])

        if self.config['tvdb']['username']:
            self.tvdb = tvdb.TheTVDB(self.config['tvdb']['username'],
                                     self.config['tvdb']['api_key'],
                                     self.config['tvdb']['user_key'])

        self.imdb = imdbutils.IMDb(self.tmdb, self.tvdb)


    def _get_trakt_lists(self):
        item_list = []  # TODO Replace with dict, scrap item_ids?
        item_ids = []

        for url in self.recipe['source_list_urls']:
            max_age = (self.recipe['new_playlist'].get('max_age', 0) if self.use_playlists
                       else self.recipe['new_library'].get('max_age', 0))
            if 'api.trakt.tv' in url:
                (item_list, item_ids) = self.trakt.add_items(
                    self.library_type, url, item_list, item_ids,
                    max_age or 0)
            elif 'imdb.com/chart' in url:
                (item_list, item_ids) = self.imdb.add_items(
                    self.library_type, url, item_list, item_ids,
                    max_age or 0)
            else:
                raise Exception("Unsupported source list: {url}".format(
                    url=url))

        if self.recipe['weighted_sorting']['enabled']:
            if self.config['tmdb']['api_key']:
                logs.info(u"Getting data from TMDb to add weighted sorting...")
                item_list = self.weighted_sorting(item_list)
            else:
                logs.warning(u"Warning: TMDd API key is required "
                             u"for weighted sorting")
        return item_list, item_ids

    def _get_plex_libraries(self):
        source_libraries = []
        for library_config in self.source_library_config:
            logs.info(u"Trying to match with items from the '{}' library ".format(
                library_config['name']))
            try:
                source_library = self.plex.server.library.section(
                    library_config['name'])
            except:  # FIXME
                raise Exception("The '{}' library does not exist".format(
                    library_config['name']))

            # FIXME: Hack until a new plexapi version is released. 3.0.4?
            if 'guid' not in source_library.ALLOWED_FILTERS:
                source_library.ALLOWED_FILTERS += ('guid',)

            source_libraries.append(source_library)
        return source_libraries

    def _get_matching_items(self, source_libraries, item_list):
        matching_items = []
        missing_items = []
        matching_total = 0
        nonmatching_idx = []
        max_count = (self.recipe['new_playlist'].get('max_count', 0) if self.use_playlists
                     else self.recipe['new_library'].get('max_count', 0))

        for i, item in enumerate(item_list):
            match = False
            if 0 < max_count <= matching_total:
                nonmatching_idx.append(i)
                continue
            res = []
            for source_library in source_libraries:
                lres = source_library.search(guid='imdb://' + str(item['id']))
                if not lres and item.get('tmdb_id'):
                    lres += source_library.search(
                        guid='themoviedb://' + str(item['tmdb_id']))
                if not lres and item.get('tvdb_id'):
                    lres += source_library.search(
                        guid='thetvdb://' + str(item['tvdb_id']))
                if lres:
                    res += lres
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
                if not self.use_playlists and self.recipe['new_library']['sort_title']['absolute']:
                    logs.info(u"{} {} ({})".format(
                        i + 1, item['title'], item['year']))
                else:
                    logs.info(u"{} {} ({})".format(
                        matching_total, item['title'], item['year']))
            else:
                missing_items.append((i, item))
                nonmatching_idx.append(i)

        if not self.use_playlists and not self.recipe['new_library']['sort_title']['absolute']:
            for i in reversed(nonmatching_idx):
                del item_list[i]

        return matching_items, missing_items, matching_total, nonmatching_idx, max_count

    def _create_symbolic_links(self, matching_items, matching_total):
        logs.info(u"Creating symlinks for {count} matching items in the "
                  u"library...".format(count=matching_total))

        try:
            if not os.path.exists(self.recipe['new_library']['folder']):
                os.mkdir(self.recipe['new_library']['folder'])
        except:
            logs.error(u"Unable to create the new library folder "
                       u"'{folder}'.".format(folder=self.recipe['new_library']['folder']))
            logs.info(u"Exiting script.")
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
                    for library_config in self.source_library_config:
                        for f in self.plex.get_library_paths(library_name=library_config['name']):
                            f = os.path.abspath(f)
                            if old_path.lower().startswith(f.lower()):
                                folder_name = os.path.relpath(old_path, f)
                                break
                        else:
                            continue

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
                            parent_path = os.path.dirname(
                                os.path.abspath(new_path))
                            if not os.path.exists(parent_path):
                                try:
                                    os.makedirs(parent_path)
                                except OSError as e:
                                    if e.errno == errno.EEXIST \
                                            and os.path.isdir(parent_path):
                                        pass
                                    else:
                                        raise
                            # Clean up old, empty directories
                            if os.path.exists(new_path) \
                                    and not os.listdir(new_path):
                                os.rmdir(new_path)

                        if (dir and not os.path.exists(new_path)) \
                                or not dir and not os.path.isfile(new_path):
                            try:
                                if os.name == 'nt':
                                    if dir:
                                        subprocess.call(['mklink', '/D',
                                                         new_path, old_path],
                                                        shell=True)
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
                                logs.error(u"Symlink failed for {path}: {e}".format(
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
                        for library_config in self.source_library_config:
                            for f in self.plex.get_library_paths(library_name=library_config['name']):
                                if old_path.lower().startswith(f.lower()):
                                    old_path = os.path.join(f,
                                                            old_path.replace(
                                                                f, '').strip(
                                                                os.sep).split(
                                                                os.sep)[0])
                                    folder_name = os.path.relpath(old_path, f)
                                    break
                            else:
                                continue

                            new_path = os.path.join(
                                self.recipe['new_library']['folder'],
                                folder_name)

                            if not os.path.exists(new_path):
                                try:
                                    if os.name == 'nt':
                                        subprocess.call(['mklink', '/D',
                                                         new_path, old_path],
                                                        shell=True)
                                    else:
                                        os.symlink(old_path, new_path)
                                    count += 1
                                    new_items.append(tv_show)
                                    updated_paths.append(new_path)
                                    done = True
                                    break
                                except Exception as e:
                                    logs.error(u"Symlink failed for {path}: {e}"
                                               .format(path=new_path, e=e))
                            else:
                                done = True
                                break

        logs.info(u"Created symlinks for {count} new items:".format(count=count))
        for item in new_items:
            logs.info(u"{title} ({year})".format(title=item.title, year=item.year))

    def _verify_new_library_and_get_items(self, create_if_not_found=False):
        # Check if the new library exists in Plex
        try:
            new_library = self.plex.server.library.section(
                self.recipe['new_library']['name'])
            logs.warning(u"Library already exists in Plex. Scanning the library...")

            new_library.update()
        except plexapi.exceptions.NotFound:
            if create_if_not_found:
                self.plex.create_new_library(
                    self.recipe['new_library']['name'],
                    self.recipe['new_library']['folder'],
                    self.library_type)
                new_library = self.plex.server.library.section(
                    self.recipe['new_library']['name'])
            else:
                raise Exception("Library '{library}' does not exist".format(
                    library=self.recipe['new_library']['name']))

        # Wait for metadata to finish downloading before continuing
        logs.info(u"Waiting for metadata to finish downloading...")
        new_library = self.plex.server.library.section(
            self.recipe['new_library']['name'])
        while new_library.refreshing:
            time.sleep(5)
            new_library = self.plex.server.library.section(
                self.recipe['new_library']['name'])

        # Retrieve a list of items from the new library
        logs.info(u"Retrieving a list of items from the '{library}' library in "
                  u"Plex...".format(library=self.recipe['new_library']['name']))
        return new_library, new_library.all()

    def _get_imdb_dict(self, media_items, item_ids, force_match=False):
        imdb_map = {}
        for m in media_items:
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
            elif force_match:
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
        return imdb_map

    def _modify_sort_titles_and_cleanup(self, item_list, imdb_map, new_library, sort_only=False):
        if self.recipe['new_library']['sort']:
            logs.info(u"Setting the sort titles for the '{}' library...".format(
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
                        new_library.key, item.ratingKey, i + 1, m['title'],
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
        if not sort_only and (
                self.recipe['new_library']['remove_from_library'] or
                self.recipe['new_library'].get('remove_old', False)):
            # Remove old items that no longer qualify
            self._remove_old_items_from_library(imdb_map=imdb_map)
        elif sort_only:
            return True
        all_new_items = self._cleanup_new_library(new_library=new_library)
        while imdb_map:
            imdb_id, item = imdb_map.popitem()
            i += 1
            logs.info(u"{} {} ({})".format(i, item.title, item.year))
            self.plex.set_sort_title(
                new_library.key, item.ratingKey, i, item.title,
                self.library_type,
                self.recipe['new_library']['sort_title']['format'],
                self.recipe['new_library']['sort_title']['visible'])
        return all_new_items

    def _remove_old_items_from_library(self, imdb_map):
        logs.info(u"Removing symlinks for items "
                  "which no longer qualify ".format(library=self.recipe['new_library']['name']))
        count = 0
        updated_paths = []
        deleted_items = []
        max_date = add_years(
            (self.recipe['new_library']['max_age'] or 0) * -1)
        if self.library_type == 'movie':
            exclude = []
            for mid, movie in imdb_map.items():
                if not self.recipe['new_library']['remove_from_library']:
                    # Only remove older than max_age
                    if not self.recipe['new_library']['max_age'] \
                            or (movie.originallyAvailableAt and
                                max_date < movie.originallyAvailableAt):
                        continue

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

                    if (dir and os.path.exists(new_path)) or (
                            not dir and os.path.isfile(new_path)):
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
                            logs.error(u"Remove symlink failed for "
                                       "{path}: {e}".format(path=new_path, e=e))
            for mid in exclude:
                imdb_map.pop(mid, None)
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
                                logs.error(u"Remove symlink failed for "
                                           "{path}: {e}".format(path=new_path,
                                                                e=e))
                        else:
                            done = True
                            break

        logs.info(u"Removed symlinks for {count} items.".format(count=count))
        for item in deleted_items:
            logs.info(u"{title} ({year})".format(title=item.title,
                                                 year=item.year))

    def _cleanup_new_library(self, new_library):
        # Scan the library to clean up the deleted items
        logs.info(u"Scanning the '{library}' library...".format(
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
        return new_library.all()

    def _run(self, share_playlist_to_all=False):
        # Get the trakt lists
        item_list, item_ids = self._get_trakt_lists()
        force_imdb_id_match = False

        # Get list of items from the Plex server
        source_libraries = self._get_plex_libraries()

        # Create a list of matching items
        matching_items, missing_items, matching_total, nonmatching_idx, max_count = self._get_matching_items(
            source_libraries=source_libraries, item_list=item_list)

        if self.use_playlists:
            # Start playlist process
            if self.recipe['new_playlist']['remove_from_playlist'] or self.recipe['new_playlist'].get('remove_old',
                                                                                                      False):
                # Start playlist over again
                self.plex.reset_playlist(playlist_name=self.recipe['new_playlist']['name'], new_items=matching_items,
                                         user_names=self.recipe['new_playlist'].get('share_to_users', []),
                                         all_users=(share_playlist_to_all if share_playlist_to_all else
                                                    self.recipe['new_playlist'].get('share_to_all', False)))
            else:
                # Keep existing items
                self.plex.add_to_playlist_for_users(playlist_name=self.recipe['new_playlist']['name'],
                                                    items=matching_items,
                                                    user_names=self.recipe['new_playlist'].get('share_to_users', []),
                                                    all_users=(share_playlist_to_all if share_playlist_to_all else
                                                               self.recipe['new_playlist'].get('share_to_all', False)))
            playlist_items = self.plex.get_playlist_items(playlist_name=self.recipe['new_playlist']['name'])
            return missing_items, (len(playlist_items) if playlist_items else 0)
        else:
            # Start library process
            # Create symlinks for all items in your library on the trakt watched
            self._create_symbolic_links(matching_items=matching_items, matching_total=matching_total)
            # Post-process new library
            logs.info(u"Creating the '{}' library in Plex...".format(
                self.recipe['new_library']['name']))
            new_library, all_new_items = self._verify_new_library_and_get_items(create_if_not_found=True)
            # Create a dictionary of {imdb_id: item}
            imdb_map = self._get_imdb_dict(media_items=all_new_items, item_ids=item_ids,
                                           force_match=force_imdb_id_match)
            # Modify the sort titles
            all_new_items = self._modify_sort_titles_and_cleanup(item_list=item_list, imdb_map=imdb_map,
                                                                 new_library=new_library, sort_only=False)
            return missing_items, len(all_new_items)

    def _run_sort_only(self):
        item_list, item_ids = self._get_trakt_lists()
        force_imdb_id_match = False

        # Get existing library and its items
        new_library, all_new_items = self._verify_new_library_and_get_items(create_if_not_found=False)
        # Create a dictionary of {imdb_id: item}
        imdb_map = self._get_imdb_dict(media_items=all_new_items, item_ids=item_ids, force_match=force_imdb_id_match)
        # Modify the sort titles
        _ = self._modify_sort_titles_and_cleanup(item_list=item_list, imdb_map=imdb_map, new_library=new_library,
                                                 sort_only=True)
        return len(all_new_items)

    def run(self, sort_only=False, share_playlist_to_all=False):
        if sort_only:
            logs.info(u"Running the recipe '{}', sorting only".format(
                self.recipe_name))
            list_count = self._run_sort_only()
            logs.info(u"Number of items in the new {library_or_playlist}: {count}".format(
                count=list_count, library_or_playlist=('playlist' if self.use_playlists else 'library')))
        else:
            logs.info(u"Running the recipe '{}'".format(self.recipe_name))
            missing_items, list_count = self._run(share_playlist_to_all=share_playlist_to_all)
            logs.info(u"Number of items in the new {library_or_playlist}: {count}".format(
                count=list_count, library_or_playlist=('playlist' if self.use_playlists else 'library')))
            logs.info(u"Number of missing items: {count}".format(
                count=len(missing_items)))
            for idx, item in missing_items:
                logs.info(u"{idx}\t{release}\t{imdb_id}\t{title} ({year})".format(
                    idx=idx + 1, release=item.get('release_date', ''),
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
                logs.warning(u"Warning: No TMDb data for {}".format(m['title']))
                continue
            m['tmdb_popularity'] = float(details['popularity'])
            m['tmdb_vote'] = float(details['vote_average'])
            m['tmdb_vote_count'] = int(details['vote_count'])
            if self.library_type == 'movie':
                if self.recipe['weighted_sorting']['better_release_date']:
                    m['release_date'] = _get_non_theatrical_release(
                        details['release_dates']) or \
                                        datetime.datetime.strptime(
                                            details['release_date'],
                                            '%Y-%m-%d').date()
                else:
                    m['release_date'] = datetime.datetime.strptime(
                        details['release_date'], '%Y-%m-%d').date()
                item_age_td = today - m['release_date']
            elif self.library_type == 'tv':
                try:
                    m['last_air_date'] = datetime.datetime.strptime(
                        details['last_air_date'], '%Y-%m-%d').date()
                except TypeError:
                    m['last_air_date'] = today
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
            if (i + 1) < m['original_idx']:
                net = Colors.GREEN + u'↑'
            elif (i + 1) > m['original_idx']:
                net = Colors.RED + u'↓'
            else:
                net = u' '
            net += str(abs(i + 1 - m['original_idx'])).rjust(3)
            try:
                # TODO
                logs.info(u"{} {:>3}: trnd:{:>3}, w_trnd:{:0<5}; vote:{}, "
                          "w_vote:{:0<5}; age:{:>4}, w_age:{:0<5}; w_rnd:{:0<5}; "
                          "w_cmb:{:0<5}; {} {}{}"
                          .format(net, i + 1, m['original_idx'],
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
