# -*- coding: utf-8 -*-
import os

from utils import YAMLBase


class ConfigParser(YAMLBase):
    def __init__(self, filepath=None):
        if not filepath:
            # FIXME?
            parent_dir = (os.path.abspath(os.path.join(
                os.path.dirname(__file__), os.path.pardir)))
            filepath = os.path.join(parent_dir, 'config.yml')

        super(ConfigParser, self).__init__(filepath)

    def validate(self):
        if not self.get('plex'):
            raise Exception("Missing 'plex' in config")
        else:
            if 'baseurl' not in self['plex']:
                raise Exception("Missing 'baseurl' in 'plex'")
            if 'token' not in self['plex']:
                raise Exception("Missing 'token' in 'plex'")

        if not self.get('trakt'):
            raise Exception("Missing 'trakt' in config")
        else:
            if 'username' not in self['trakt']:
                raise Exception("Missing 'username' in 'trakt'")
            if 'client_id' not in self['trakt']:
                raise Exception("Missing 'client_id' in 'trakt'")
            if 'client_secret' not in self['trakt']:
                raise Exception("Missing 'client_secret' in 'trakt'")

        return True
