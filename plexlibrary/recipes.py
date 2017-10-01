# -*- coding: utf-8 -*-
import glob
import os

from utils import YAMLBase


class RecipeParser(YAMLBase):
    def __init__(self, name, directory=None):
        self.name = name.strip('.yml')
        recipe_file = self.name + '.yml'  # TODO support .yaml
        # FIXME?
        if not directory:
            parent_dir = (os.path.abspath(os.path.join(os.path.dirname(__file__),
                os.path.pardir)))
            directory = os.path.join(parent_dir, 'recipes')

        filepath = os.path.join(directory, recipe_file)

        super(RecipeParser, self).__init__(filepath)

    def dump(self):
        print(self.data)


def get_recipes(directory=None):
    if not directory:
        parent_dir = (os.path.abspath(os.path.join(os.path.dirname(__file__),
            os.path.pardir)))
        directory = os.path.join(parent_dir, 'recipes')

    recipes = []
    for path in glob.glob(directory + '/*.yml'):
        d, filename = os.path.split(path)
        recipe_name = filename.strip('.yml')
        recipes.append(recipe_name)
    recipes.sort()

    return recipes

