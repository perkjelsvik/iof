Backend
=======

Here is the documentation for Backend code. If everything is configured corretly,
starting up is as simple as running

.. code-block::

  python -m src.backend.main

This will spawn an instance of :code:`src.backend.mqttclient` using the configurations
of the project.

For first time start-up:

.. code-block::

   python -m src.backend.main -i
   Please input ip-address: 127.0.0.1
   and port number: 8883
   username: mqttuser
   Password: mqttpassword

You will be prompted to fill in :code:`mqtt` broker information. By default, it will
set the main database name to :code:`iof.db` and backup database to
:code:`backupDB.db` inside :code:`src/backend/dbmanager/databases/`. You can run
:code:`main.py` with argument :code:`-db` and then provide one argument to name
main database something else, two arguments to name both main and backup database
something else

.. code-block::

   python -m src.backend.main -i -db "mainDatabaseName" "backupDatabaseName"

You can also reset :code:`backend` with the :code:`-r` flag. To see all arguments,
run :code:`python -m src.backend.main -h`.

Make sure to include a :code:`metadata.toml` file inside :code:`src/backend/.config/`
correctly formatted to have backend running correctly. When initing, it will
automatically build other metadata-files correctly.

Top-level modules
-----------------

main
~~~~


.. automodule:: src.backend.main
    :members:
    :undoc-members:

mqttclient
~~~~~~~~~~

.. automodule:: src.backend.mqttclient
    :members:
    :undoc-members:

initbackend
~~~~~~~~~~~

.. automodule:: src.backend.initbackend
    :members:
    :undoc-members:

Message handling
----------------

conversion
~~~~~~~~~~

.. automodule:: src.backend.msghandler.conversion
    :members:
    :undoc-members:

msghandler
~~~~~~~~~~

.. automodule:: src.backend.msghandler.msghandler
    :members:
    :undoc-members:

packet
~~~~~~

.. automodule:: src.backend.msghandler.packet
    :members:
    :undoc-members:

protocol
~~~~~~~~

.. automodule:: src.backend.msghandler.protocol
    :members:
    :undoc-members:

Databasemanager
---------------

dbformat
~~~~~~~~

.. automodule:: src.backend.dbmanager.dbformat
    :members:

dbinit
~~~~~~

.. automodule:: src.backend.dbmanager.dbinit
    :members:

dbmanager
~~~~~~~~~

.. automodule:: src.backend.dbmanager.dbmanager
    :members:


msgbackup
~~~~~~~~~

.. automodule:: src.backend.dbmanager.msgbackup
    :members:

msgconversion
~~~~~~~~~~~~~

.. automodule:: src.backend.dbmanager.msgconversion
    :members:

positioning
~~~~~~~~~~~

.. automodule:: src.backend.dbmanager.positioning
    :members:

tdoa
~~~~

.. automodule:: src.backend.dbmanager.tdoa
    :members:

