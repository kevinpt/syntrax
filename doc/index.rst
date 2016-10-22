=======
Syntrax
=======

Syntrax is a railroad diagram generator. It creates visual illustration of the grammar used for programming languages. A specification file describes the syntax as a hierarchy of basic elements. This is processed into an image representing the same syntax with interconnected bubbles.

Syntrax can render to PNG bitmap images or SVG, PDF, PS, and EPS vector images. The SVG output can have hyperlinked text allowing users to quickly navigate to documentation of different syntax elements.

Syntrax is a heaviliy modified version of the railroad diagram generator used for the `SQLite documentation <https://www.sqlite.org/lang.html>`_. The generator has been ported to Python, converted to use the Cairo rendering backend, and enhanced with configurable layout options.



Requirements
------------

Syntrax requires either Python 2.7 or Python 3.x, Pycairo, and Pango.

The installation script depends on setuptools which will be installed if it
isn't currently present in your Python distribution. The source is written in
Python 2.7 syntax but will convert cleanly to Python 3 when the installer
passes it through 2to3.

Licensing
---------

Syntrax is licensed for free commercial and non-commercial use under the terms of the MIT license.


Download
--------

You can access the Syntrax Git repository from `Github
<https://github.com/kevinpt/syntrax>`_. You can install direct from PyPI with the "pip"
command if you have it available.


Installation
------------

Syntrax is a Python package. You must have Python installed first to use it. Most modern Linux distributions and OS/X have it available by default. There are a number of options available for Windows. If you don't already have a favorite, I recommend getting one of the `"full-stack" Python distros <http://www.scipy.org/install.html>`_ that are geared toward scientific computing such as Anaconda or Python(x,y).

If your OS has a package manager, it may be preferable to install Python setuptools through that tool before attempting to install Syntrax. Otherwise, the installation script will install these packages directly without registering them with the OS package manager.

The easiest way to install Syntrax is from `PyPI <https://pypi.python.org/pypi/sytrax>`_.

.. code-block:: sh

  > pip install --upgrade syntrax

This will download and install the latest release, upgrading if you already have it installed. If you don't have ``pip`` you may have the ``easy_install`` command available which can be used to install ``pip`` on your system:

.. code-block:: sh

  > easy_install pip
  
You can also use ``pip`` to get the latest development code from Github:

.. code-block:: sh

  > pip install --upgrade https://github.com/kevinpt/syntrax/tarball/master

If you manually downloaded a source package or created a clone with Git you can install Syntrax with the following command run from the base Syntrax directory:

.. code-block:: sh

  > python setup.py install

On Linux systems you may need to install with root privileges using the *sudo* command.

After a successful install the Syntrax package and script will be available. On Linux they should be immediately accessible from your current search path. On Windows you will need to make sure that the ``<Python root>\Scripts`` directory is in your %PATH% environment variable.

If you can't use the installer script, it is possible to use ``syntrax.py`` directly without installation and just distribute it along with your code. If you need to use this module from Python 3 you can manually convert it with the ``2to3`` tool:

.. code-block:: sh

  > 2to3 -w syntrax.py



.. toctree::
   :maxdepth: 1
   :hidden:

Indices and tables
------------------

* :ref:`genindex`
* :ref:`search`

