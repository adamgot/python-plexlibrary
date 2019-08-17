# -*- coding: utf-8 -*-
from datetime import datetime

import ruamel.yaml


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
        self.filename = filename

        yaml = ruamel.yaml.YAML()
        yaml.preserve_quotes = True
        with open(self.filename, 'r') as f:
            try:
                self.data = yaml.load(f)
            except ruamel.yaml.YAMLError as e:
                raise e

    def __getitem__(self, k):
        return self.data[k]

    def __iter__(self, k):
        return self.data.itervalues()

    def __setitem__(self, k, v):
        self.data[k] = v

    def get(self, k, default=None):
        if k in self.data:
            return self.data[k]
        else:
            return default

    def save(self):
        yaml = ruamel.yaml.YAML()
        with open(self.filename, 'w') as f:
            yaml.dump(self.data, f)


def add_years(years, from_date=None):
    if from_date is None:
        from_date = datetime.now()
    try:
        return from_date.replace(year=from_date.year + years)
    except ValueError:
        # Must be 2/29!
        return from_date.replace(month=2, day=28,
                                 year=from_date.year + years)
