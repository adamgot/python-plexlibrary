Python-PlexLibrary
==================

Python command line utility for creating and maintaining dynamic Plex
libraries based on "recipes".

E.g. Create a library consisting of all movies or tv shows in a Trakt_ list or
on an IMDb_ chart that exist in your main library, and set the sort titles
accordingly.

.. _Trakt: https://trakt.tv/
.. _IMDb: https://imdb.com/

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

  * Required for matching movies and some TV shows sourced from IMDb

* (optional) TheTVDB API

  * https://www.thetvdb.com/?tab=apiregister
    
  * Required for matching any library items that use the TheTVDB agent with the items from the lists (if those items do not include a TheTVDB ID)
    
  * Shouldn't be necessary for Trakt, as those usually all have TVDB IDs.

  * Required for matching TV shows sourced from IMDb

Getting started
---------------

1. Clone or download this repo.

2. Install Python and pip if you haven't already.

3. Install the requirements:

   .. code-block:: shell

       pip install -r requirements.txt

4. Copy config-template.yml to config.yml and edit it with your information.

  * Here's a guide if you're unfamiliar with YAML syntax. **Most notably you need to use spaces instead of tabs!** http://docs.ansible.com/ansible/latest/YAMLSyntax.html

5. Check out the recipe examples under recipes/examples. Copy an example to recipes/ and edit it with the appropriate information.

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
    
**(If you're on Windows, you might have to run as admin)**

When you're happy with the results, automate the recipe in cron_ or equivalent (automated tasks in Windows https://technet.microsoft.com/en-us/library/cc748993(v=ws.11).aspx).

.. _cron: https://code.tutsplus.com/tutorials/scheduling-tasks-with-cron-jobs--net-8800

**Pro tip!** Edit the new library and uncheck *"Include in dashboard"*. Othewise if you start watching something that exists in multiple libraries, all items will show up on the On Deck. This makes it so that only the item in your main library shows up.

Planned features
----------------
See issues.

Credit
------
Original functionality is based on https://gist.github.com/JonnyWong16/b1aa2c0f604ed92b9b3afaa6db18e5fd

Custom Python Plexlibrary Recipes
---------------------------------
I have added my current recipes I have made for Custom Python Plexlibrary Recipes for some of my lists.

https://github.com/adamgot/python-plexlibrary

These recipes will run out of the box for PTS users.

Do one recipe at a time and when it pops up in plex edit the lib and remove from dashboard, disable thumbnails, disable cinema trailers and finally disable collections. When creating new libs with receipes it will trigger a scan but its quite quick and doesnt effect anything else being added with PAS.

To update your custom libs weekly drop the plexlibrary.sh from the scripts folder in the repo into /opt/appdata/python-plexlibrary.

.. code-block:: shell

    chmod +x /opt/appdata/python-plexlibrary/plexlibrary.sh

Then open cron with.

.. code-block:: shell

    crontab -e

Then add a cron at the bottom of the file

.. code-block:: shell

    @weekly bash /opt/appdata/python-plexlibrary/plexlibrary.sh >/dev/null 2>&1

If you would like to keep your series lists up to date with traktarr (you must have this set up already) then do the following:

Edit the series lists to your liking

.. code-block:: shell

    nano /opt/appdata/python-plexlibrary/scripts/seriesupdate.sh

Save with **ctrl+o** and then close with **ctrl+x**

Open cron with

.. code-block:: shell

    crontab -e

Then add a cron at the bottom of the file

.. code-block:: shell

    @weekly bash /opt/appdata/python-plexlibrary/scripts/seriesupdate.sh >/dev/null 2>&1
