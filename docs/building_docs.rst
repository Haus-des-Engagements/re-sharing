.. _building_docs:

Building Documentation Locally
==============================

This guide explains how to build the Re-Sharing documentation locally on your machine.

Prerequisites
------------

Before building the documentation, make sure you have installed all the required dependencies.
These are included in the ``requirements/local.txt`` file and include:

* sphinx==8.1.3
* sphinx-autobuild==2024.10.3
* sphinx-rtd-theme==3.0.2

If you haven't installed these yet, you can do so by running:

.. code-block:: bash

    pip install -r requirements/local.txt

Building the Documentation
-------------------------

The documentation uses Sphinx and can be built using the provided Makefile in the ``docs`` directory.

To build the HTML documentation:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Navigate to the ``docs`` directory:

   .. code-block:: bash

       cd docs

2. Build the HTML documentation:

   .. code-block:: bash

       make html

   This will build the HTML documentation in the ``_build/html`` directory.

3. Open the documentation in your browser:

   .. code-block:: bash

       # On Linux
       xdg-open _build/html/index.html

       # On macOS
       open _build/html/index.html

       # On Windows
       start _build/html/index.html

Using Live Reload
~~~~~~~~~~~~~~~~

For a better development experience, you can use the ``livehtml`` target which will start a server
with auto-reload capability:

.. code-block:: bash

    make livehtml

This will start a development server at http://localhost:9000/ that automatically rebuilds the
documentation when you make changes to the source files.

Building API Documentation
~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to generate API documentation from the Django application code:

.. code-block:: bash

    make apidocs

This will create RST files in the ``api`` directory that document the Python modules in the project.

Other Build Options
~~~~~~~~~~~~~~~~~

To see all available build options:

.. code-block:: bash

    make help

This will show you all the available targets in the Makefile, including:

* ``clean``: Remove the build directory
* ``html``: Build HTML documentation
* ``latexpdf``: Build PDF documentation using LaTeX
* And many more...

Troubleshooting
--------------

If you encounter any issues while building the documentation:

1. Make sure all dependencies are installed correctly
2. Check that you're in the correct directory (``docs``)
3. Look for error messages in the build output
4. Try cleaning the build directory with ``make clean`` before rebuilding

For issues with the ``libmagic`` library (used by ``python-magic``), you may need to install system dependencies:

.. code-block:: bash

    # On Ubuntu/Debian
    sudo apt-get install libmagic-dev

    # On macOS
    brew install libmagic

    # On Windows
    # Follow instructions at https://github.com/ahupp/python-magic#windows
