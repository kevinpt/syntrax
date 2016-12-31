.. image:: http://kevinpt.github.io/syntrax/_static/syntrax_icon.png

=======
Syntrax
=======

Syntrax is a railroad diagram generator. It creates a visual illustration of the grammar used for programming languages. A specification file describes the syntax as a hierarchy of basic elements. This is processed into an image representing the same syntax with interconnected bubbles.

The specification is a set of nested Python function calls:

.. code-block::

  indentstack(10,
    line(opt('-'), choice('0', line('1-9', loop(None, '0-9'))),
      opt('.', loop('0-9', None))),

    line(opt(choice('e', 'E'), choice(None, '+', '-'), loop('0-9', None)))
  )

This is processed by Syntrax to generate an SVG image:

.. image:: http://kevinpt.github.io/syntrax/_static/json_number.png

JSON number syntax


Syntrax can render to PNG bitmap images or SVG, PDF, PS, and EPS vector images. The SVG output can have `hyperlinked text <http://kevinpt.github.io/syntrax/index.html#hyperlinked-text>`_ allowing users to quickly navigate to documentation of different syntax elements.

Syntrax is a heavily modified version of the railroad diagram generator used for the `SQLite documentation <https://www.sqlite.org/lang.html>`_. The generator has been ported to Python, converted to use the Cairo rendering backend, and enhanced with configurable layout options.



Requirements
------------

Syntrax requires either Python 2.7 or Python 3.x, Pycairo, and Pango.

The installation script depends on setuptools which will be installed if it
isn't currently present in your Python distribution. The source is written in
Python 2.7 syntax but will convert cleanly to Python 3 when the installer
passes it through 2to3.

The Pango library is used compute the dimensions of a text layout. There is no standard package to get the Pango Python bindings installed. It is a part of the Gtk+ library which is accessed either through the PyGtk or PyGObject APIs, both of which are supported by Syntrax. You should make sure that one of these libraries is available before installing Syntrax. A `Windows installer <http://www.pygtk.org/downloads.html>`_ is available. For Linux distributions you should install the relevant libraries with your package manager.


Download
--------

You can access the Syntrax Git repository from `Github
<https://github.com/kevinpt/syntrax>`_. You can install direct from PyPI with the "pip"
command if you have it available.


Documentation
-------------

The full documentation is available online at the `main Syntrax site
<http://kevinpt.github.io/syntrax/>`_.

