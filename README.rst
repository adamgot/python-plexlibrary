Python-PlexLibrary
==================

Python command line utility for creating and maintaining dynamic Plex
libraries based on "recipes".

E.g. Create a library consisting of all movies or tv shows in a Trakt_ list or
on an IMDb_ chart that exist in your main library, and set the sort titles
accordingly.

.. _Trakt: https://trakt.tv/
.. _IMDb: https://imdb.com/

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

  .. code-block:: shell

      cp /opt/appdata/python-plexlibrary/config-template.yml /opt/appdata/python-plexlibrary/config.yml

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
    
Custom Python Plexlibrary Recipes
---------------------------------
I have added my current recipes I have made for Python Plexlibrary using some of Porkie16 lists.

https://github.com/adamgot/python-plexlibrary

https://github.com/porkie02/trakt

These recipes will run out of the box for PTS users.

Do one recipe at a time and when it pops up in plex, edit the library and uncheck 'Include in dashboard', uncheck 'Enable video preview thumbnails' and finally disable collections (from the drop down). When creating new library with receipes, it will trigger a scan but its quite quick and doesn't effect anything else being added with PAS. Just as a precaution, stop all downloads until the library has finished being added.

Update your custom plex libraries weekly
----------------------------------------

make it executable with the following.

.. code-block:: shell

    chmod +x /opt/appdata/python-plexlibrary/plexlibrary.sh

Then open cron with.

.. code-block:: shell

    crontab -e

Then add this line to the bottom of the file.

.. code-block:: shell

    @weekly bash /opt/appdata/python-plexlibrary/plexlibrary.sh >/dev/null 2>&1
    
save and exit with **ctrl+o** & **ctrl+x**.

Keep your series lists up to date with traktarr
-----------------------------------------------

First of all, make sure you have this set up correctly https://github.com/PTS-Team/PTS-Team/wiki/Traktarr

Then, edit the series lists to your liking. I have provided some of my favourite ones for you.

.. code-block:: shell

    nano /opt/appdata/python-plexlibrary/scripts/seriesupdate.sh

save and exit with **ctrl+o** & **ctrl+x**.

make it executable with the following.

.. code-block:: shell

    chmod +x /opt/appdata/python-plexlibrary/scripts/seriesupdate.sh

Open cron with

.. code-block:: shell

    crontab -e

Then add a cron at the bottom of the file

.. code-block:: shell

    @weekly bash /opt/appdata/python-plexlibrary/scripts/seriesupdate.sh >/dev/null 2>&1

Creating your own recipe
------------------------

If you would like to create your own recipe then just copy the recipe and adjust the details to suit.

Example

.. code-block:: shell

    cp /opt/appdata/python-plexlibrary/recipes/tv_amazon.yml /opt/appdata/python-plexlibrary/recipes/tv_hulu.yml
    
.. code-block:: shell

    nano /opt/appdata/python-plexlibrary/recipes/tv_hulu.yml
