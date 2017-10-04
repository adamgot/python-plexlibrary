# -*- coding: utf-8 -*-
import yaml
from yaml import Loader, SafeLoader


class Colors(object):
    RED = u'\033[1;31m'
    BLUE = u'\033[1;34m'
    CYAN = u'\033[1;36m'
    GREEN = u'\033[0;32m'
    RESET = u'\033[0;0m'
    BOLD = u'\033[;1m'
    REVERSE = u'\033[;7m'


class YAMLBase(object):
    def __init__(self, filename):
        # Make sure pyyaml always returns unicode
        def construct_yaml_str(self, node):
            return self.construct_scalar(node)
        Loader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)
        SafeLoader.add_constructor(u'tag:yaml.org,2002:str',
                                   construct_yaml_str)

        with open(filename, 'r') as f:
            try:
                self.data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise e

    def __getitem__(self, k):
        return self.data[k]

    def __iter__(self, k):
        return self.data.itervalues()
