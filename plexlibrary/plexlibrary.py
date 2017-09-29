# -*- coding: utf-8 -*-
"""Automated Plex library utility

This utility creates or maintains a Plex library
based on a configuration recipe.

Disclaimer:
    Use at your own risk! I am not responsible
    for damages to your Plex server or libraries.

Credit:
    Originally based on https://gist.github.com/JonnyWong16/f5b9af386ea58e19bf18c09f2681df23
    by /u/SwiftPanda16
"""

import argparse
import sys

from recipe import Recipe

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', help='Create a library using this recipe')
    parser.add_argument('-s', '--sort-only', action='store_true', help='Only sort the library')
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    r = Recipe(args.recipe)
    r.run(args.sort_only)
