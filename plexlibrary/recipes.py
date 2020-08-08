# -*- coding: utf-8 -*-
import glob
import os

import logs

from utils import YAMLBase


class RecipeParser(YAMLBase):
    def __init__(self, name, directory=None):
        # TODO accept filename
        self.name = os.path.splitext(name)[0]
        recipe_file = self.name + '.yml'  # TODO support .yaml
        # FIXME?
        if not directory:
            parent_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), os.path.pardir))
            directory = os.path.join(parent_dir, 'recipes')

        filepath = os.path.join(directory, recipe_file)

        super(RecipeParser, self).__init__(filepath)

    def dump(self):
        logs.info(self.data)

    def validate(self, use_playlists: bool = False):
        if not self.get('library_type'):
            raise Exception("Missing 'library_type' in recipe")
        else:
            if not self['library_type'].lower().startswith('movie') \
                    and not self['library_type'].lower().startswith('tv'):
                raise Exception("'library_type' should be 'movie' or 'tv'")

        if not self.get('source_list_urls'):
            raise Exception("Missing 'source_list_urls' in recipe")

        if not self.get('source_libraries'):
            raise Exception("Missing 'source_libraries' in recipe")
        else:
            for i in self['source_libraries']:
                if 'name' not in i:
                    raise Exception("Missing 'name' in 'source_libraries'")

        if use_playlists:  # check new_playlist section
            if not self.get('new_playlist'):
                raise Exception("Missing 'new_playlist' in recipe")
            else:
                if not self['new_playlist'].get('name'):
                    raise Exception("Missing 'name' in 'new_playlist'")

        else:  # check new_library section
            if not self.get('new_library'):
                raise Exception("Missing 'new_library' in recipe")
            else:
                if not self['new_library'].get('name'):
                    raise Exception("Missing 'name' in 'new_library'")
                if not self['new_library'].get('folder'):
                    raise Exception("Missing 'folder' in 'new_library'")
                if self['new_library'].get('sort_title'):
                    if 'format' not in self['new_library']['sort_title']:
                        raise Exception("Missing 'format' in 'sort_title'")
                    if 'visible' not in self['new_library']['sort_title']:
                        raise Exception("Missing 'visible' in 'sort_title'")
                    if 'absolute' not in self['new_library']['sort_title']:
                        raise Exception("Missing 'absolute' in 'sort_title'")

        if not self.get('weighted_sorting'):
            raise Exception("Missing 'weighted_sorting' in recipe")
        else:
            if 'enabled' not in self['weighted_sorting']:
                raise Exception("Missing 'enabled' in 'weighted_sorting'")
            else:
                if 'better_release_date' not in self['weighted_sorting']:
                    raise Exception("Missing 'better_release_date' in 'weighted_sorting'")
                if 'weights' not in self['weighted_sorting']:
                    raise Exception("Missing 'weights' in 'weighted_sorting'")
                else:
                    if 'index' not in self['weighted_sorting']['weights']:
                        raise Exception("Missing 'index' in 'weights'")
                    if 'vote' not in self['weighted_sorting']['weights']:
                        raise Exception("Missing 'vote' in 'weights'")
                    if 'age' not in self['weighted_sorting']['weights']:
                        raise Exception("Missing 'age' in 'weights'")
                    if 'random' not in self['weighted_sorting']['weights']:
                        raise Exception("Missing 'random' in 'weights'")
                    if 'genre_bias' not in self['weighted_sorting']['weights']:
                        raise Exception("Missing 'genre_bias' in 'weights'")

        return True


def get_recipes(directory=None):
    if not directory:
        parent_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), os.path.pardir))
        directory = os.path.join(parent_dir, 'recipes')

    recipes = []
    for path in glob.glob(os.path.join(directory, '*.yml')):
        d, filename = os.path.split(path)
        recipe_name = os.path.splitext(filename)[0]
        recipes.append(recipe_name)
    recipes.sort()

    return recipes
