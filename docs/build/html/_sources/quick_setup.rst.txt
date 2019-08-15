Setup for new :code:`iof` projects
==================================

In this page you will find detailed information on how to setup :code:`iof`
for a new project. First a quick setup outlining the steps. In the sections
below, more detailed instructions for the individual steps are given.

Quick setup
-----------

1. Download the code from https://github.com/perkjelsvik/iof
2. Create a virtual environment inside repository and install project packages
3. Fill out your project metadata and save it to a file :code:`metadata.xlsx` in root location of repository code
4. Run :code:`python -m src.backend.main -i`
5. Answer :code:`y` to convert excel metadata and fill in MQTT broker information
6. Keep backend running or :code:`Ctrl+C` to kill it.
7. Navigate to :code:`src/frontend` and run :code:`python initfrontend.py`
8. Fill in at least one username/password pair for Dash app authentication
9. Run :code:`python iof_app.py` to start project Dash app
10. If there is data in the main database inside backend, go to :code:`http://127.0.0.1:8050` to explore the app


Installing Python 3.7
---------------------

Windows 10
^^^^^^^^^^

The latest release of Python can be downloaded from https://www.python.org/downloads/. 
The currently most recent python version is :code:`3.7.4`. If you are on windows, 
download for example the executable installer and use that to install. It is 
recommended to add to PATH and to also allow the installer to extend the PATH length
limit of the system. For the following commands, it is assumed you are using the
:code:`cmd.exe` terminal. You can of course use other terminals too, but for this
guide, the commands provided are valid for :code:`cmd.exe`. Translate to your own
terminal as appropiate. 

Open :code:`cmd.exe` and verify your Python version by entering :code:`python -v`.
It should read out the version you installed. If not, there might be issues with 
python on PATH. Typically it is due to multiple python installations on the same
machine so that it does not know which version to point too. There are several guides
on how to fix these issues if you google a bit.

Alternatively, you could install the Windows 10 Linux Subsystem https://docs.microsoft.com/en-us/windows/wsl/install-win10 

Linux Ubuntu
^^^^^^^^^^^^

.. code-block::

    sudo apt-get install python3.7 python3.7-venv

Downloading :code:`iof` repository
----------------------------------

Clone / download the repository code from https://github.com/iof.
Here is the direct download link for the latest version https://github.com/PerKjelsvik/iof/archive/master.zip.
Unzip it in your desired location. 

If you have git installed in your terminal, you can clone it to your desired location directly like so:

.. code-block::
    
    git clone https://github.com/perkjelsvik/iof


Installing repository dependencies
----------------------------------

You should use a virtual environment. Any will work, but the recommended to use is the
built-in :code:`venv` https://docs.python.org/3/library/venv.html. Inside the repository
you have downloaded, run from terminal

.. code-block::

    windows: python -m venv venv 
    ubuntu: python3.7 -m venv venv

This will create a :code:`venv` folder in root of the repository. You need to activate this
environment everytime to run iof. To activate:

.. code-block::

    windows: venv\Scripts\activate
    linux: source venv/bin/activate OR . venv/bin/activate

You should now se :code:`(venv)` to the left in your terminal. This indicates that the environment
is activated. To deactivate enter :code:`deactivate`. Keep the enviornment activated. Next is to
install code dependencies. When using :code:`python` in terminal it will now point to the python3.7
version of the virtual environment, and the packages installed within. All the following commands 
should work on both windows and linux. Begin by upgrading :code:`pip` and then install the packages
used by the repository

.. code-block::

    pip install --upgrade pip
    pip install -r requirements_dev.txt

You are now ready to initalize your project.


Filling out :code:`metadata.xlsx`
---------------------------------

To position tags, convert raw data, and for the frontend Dash app to work, you need metadata.
In the repository there is a file, :code:`metadata_example.xlsx`, that you can use as a reference.
The file is also available here: https://docs.google.com/spreadsheets/d/e/2PACX-1vT5kx0npXn5d-5JLvW7uCfPEsXMts3d7dilHhqMWyXCn_6CNW_eRccCBxAkIZyq5bzEy-wUFNY3gZ3Y/pubhtml 

Inside the document there are instructions on how to fill the individual sheets. I recommmend 
duplicating the example file, and renaming the copy to :code:`metadata.xlsx`. The file must
have that name for the code to recognize it later. When you modify the file, remember to remove
the blue rows of each sheet, namely the row below the column names explaining what the column is.
If not the code will most likely crash in attempts to read out information from this row.
The about sheet can be changed freely.

Initalizing backend
-------------------

From the root location of the repository, run

.. code-block::

   python -m src.backend.main -i

Follow the prompts to initalize the backend. After filling in MQTT information, the 
program will spawn the iof backend as a subprocess and try to subscribe to broker. If
there are no issues it will run forever. If it crashes, for example due to no connection
to broker, it will attempt to respawn infinitely. Kill it with :code:`Ctrl+C`. Here 
is an example of the information you will fill:

.. code-block::

   [...] Do you wish to convert metadata from an excel (xlsx) file? [y/n]: y
   Please input ip-address: 127.0.0.1
   and port number: 1883
   username: mqttuser
   Password: mqttpassword

If you for any reason kill the backend / it stops completely, and you don't need to initalize 
it again, you can run the same :code:`python -m src.backend.main` command with the :code:`-i`
flag. If you do need to change it, run it again with the flag, potentially with the :code:`-r`
flag to, if you need to reset completely. To see all avalable commands, use the :code:`-h` flag.

Alternatively, you can navigate to :code:`src/backend/.config/` and modify the files stored there
manually. :code:`metadata.toml` is the converted excel metadata, while :code:`config.toml` is the
MQTT broker configuration. Additionally, there is :code:`db_names.toml`, :code:`topics.toml`, 
:code:`metadata_conversion.toml`, and :code:`metadata_positioning.toml`. 


Initializing frontend
---------------------

Due to the way the Dash app is structured, the code must be run from 
inside the :code:`src/frontend/` folder. Navigate there, and for first-time
setup, run

.. code-block::

    python initfrontend.py

This will only work if backend has already been correctly initalized. If so,
the metadata for the current project will be converted to a frontend-compatible
file. It will then prompt you to add at least one username/password pair:

.. code-block::

    python initfrontend.py
    Done converting backend metadata to frontend metadata
    At least one username/password pair is needed for authentication.
    It will be stored next to the dash app in a toml file in plain text.
    username: dev
    password: pass
    Do you wish to add another username/password pair? [y/n]: n
    Successfully added username/password pair(s) to file! can now authenticate in Dash app.

You are now ready to run the Dah app. To run, simply run

.. code-block::

    python iof_app.py

and then go visit https://127.0.0.1:8050 in your web browser. This should load the 
iof Dash app, polling data from the main database located in :code:`src/backend/dbmanager/databases/`,
and using metadata to provide filtering options in the app. Use the username/password combination
you provided in the initalization.

The app is essentially a Flask app. Look up how to host Flask apps on webservers / other solutions for 
ways to make the app publicly available. The code you would have to change is the very last line of code
in :code:`iof_app.py`. 

.. figure:: images/webpage.png
    :width: 100%
    :align: center
    :alt: Dash iof web app