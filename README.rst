Python-PlexLibrary
==================

Python command line utility for creating and maintaining dynamic Plex
libraries based on "recipes".

E.g. Create a library consisting of all movies or tv shows in a Trakt_
list that exist in your main library, and set the sort titles
accordingly.

.. _Trakt: https://trakt.tv/

Disclaimer
----------
This is still a work in progress, so major changes may occur in new versions.

Requirements
------------
* You need a trakt.tv account and an API app: https://trakt.tv/oauth/applications/new
* (optional) The Movie Database API
    * https://developers.themoviedb.org/3/getting-started
    * Required for fetching scores, release dates etcetera, for weighted sorting 
    * Required for matching any library items that use the TMDb agent with the items from the lists (if those items do not include a TMDb ID)
    * Shouldn't be necessary for Trakt, as those usually all have TMDb IDs.
* (optional) TheTVDB API
    * https://www.thetvdb.com/?tab=apiregister
    * Required for matching any library items that use the TheTVDB agent with the items from the lists (if those items do not include a TheTVDB ID)
    * Shouldn't be necessary for Trakt, as those usually all have TVDB IDs.

Getting started
---------------

1. Clone or download this repo.
2. Install Python and pip if you haven't already.
3. Install the requirements:

   .. code-block:: shell

       pip install -r requirements.txt

4. Copy config-template.yml to config.yml and edit it with your information.
5. Check out the recipe examples under recipes/examples. Copy an example to recipes/ and edit it with the appropriate information.

    * Note: multiple source libraries are currently not supported https://github.com/adamgot/python-plexlibrary/issues/4

Usage
-----
In the base directory, run:

.. code-block:: shell

    python plexlibrary -h

for details on how to use the utility.

.. code-block:: shell

    python plexlibrary -l

lists available recipes.

To run a recipe named "movies_trending", run:

.. code-block:: shell

    python plexlibrary movies_trending

When you're happy with the results, automate the recipe in cron_ or equivalent (automated tasks in Windows https://technet.microsoft.com/en-us/library/cc748993(v=ws.11).aspx).

.. _cron: https://code.tutsplus.com/tutorials/scheduling-tasks-with-cron-jobs--net-8800

**Pro tip!** Edit the new library and uncheck *"Include in dashboard"*. Othewise if you start watching something that exists in multiple libraries, all items will show up on the On Deck. This makes it so that only the item in your main library shows up.

Planned features
----------------
* PEP8 compliance, and still lots of restructuring to be done.
* Proper logging.
* Support for multiple source libraries
* Support for more source lists, including none at all to consider every item in the source libraries.
* Support for filters based on various criteria like genre, score, language, collections etc.
* Better release dates for movies and tv shows, maybe pulling from preDB.
* Support for creating playlists and adding to collections instead of creating new libraries.
* Support for other operations rather than just symbolic links, especially moving items completely to a new library.

Credit
------
Original functionality is based on https://gist.github.com/JonnyWong16/f5b9af386ea58e19bf18c09f2681df23

