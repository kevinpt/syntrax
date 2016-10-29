=======
Syntrax
=======

Syntrax is a railroad diagram generator. It creates a visual illustration of the grammar used for programming languages. A specification file describes the syntax as a hierarchy of basic elements. This is processed into an image representing the same syntax with interconnected bubbles.

The specification is a set of nested Python function calls:

.. code-block:: python

  indentstack(10,
    line(opt('-'), choice('0', line('1-9', loop(None, '0-9'))),
      opt('.', loop('0-9', None))),

    line(opt(choice('e', 'E'), choice(None, '+', '-'), loop('0-9', None)))
  )

This is processed to generate an SVG image:

.. figure:: images/json_number.svg
  :align: center

  JSON number syntax


Syntrax can render to PNG bitmap images or SVG, PDF, PS, and EPS vector images. The SVG output can have hyperlinked text allowing users to quickly navigate to documentation of different syntax elements.

Syntrax is a heaviliy modified version of the railroad diagram generator used for the `SQLite documentation <https://www.sqlite.org/lang.html>`_. The generator has been ported to Python, converted to use the Cairo rendering backend, and enhanced with configurable layout options.



Requirements
------------

Syntrax requires either Python 2.7 or Python 3.x, Pycairo, and Pango.

The installation script depends on setuptools which will be installed if it
isn't currently present in your Python distribution. The source is written in
Python 2.7 syntax but will convert cleanly to Python 3 when the installer
passes it through 2to3.

The Pango library is used compute the dimensions of a text layout. There is no standard package to get the Pango Python bindings installed. It is a part of the Gtk+ library which is accessed either through the PyGtk or PyGObject APIs, both of which are supported by Syntrax. You should make sure that one of these libraries is available before installing Syntrax.

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

Syntrax is a Python application. You must have Python installed first to use it. Most modern Linux distributions and OS/X have it available by default. There are a number of options available for Windows. If you don't already have a favorite, I recommend getting one of the `"full-stack" Python distros <http://www.scipy.org/install.html>`_ that are geared toward scientific computing such as Anaconda or Python(x,y).

If your OS has a package manager, it may be preferable to install Python setuptools through that tool before attempting to install Syntrax. Otherwise, the installation script will install these packages directly without registering them with the OS package manager.

The easiest way to install Syntrax is from `PyPI <https://pypi.python.org/pypi/syntrax>`_.

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

After a successful install the Syntrax command line application will be available. On Linux they should be immediately accessible from your current search path. On Windows you will need to make sure that the ``<Python root>\Scripts`` directory is in your %PATH% environment variable.

If you can't use the installer script, it is possible to use ``syntrax.py`` directly without installation. If you need to use Python 3 you can manually convert it with the ``2to3`` tool:

.. code-block:: sh

  > 2to3 -w syntrax.py

Using Syntrax
-------------

Syntrax is a command line tool. You pass it an input specification file and it will generate a diagram in any of the supported output formats.

.. parsed-literal::

  usage: syntrax.py [-h] [-i INPUT] [-o OUTPUT] [-s STYLES] [--title TITLE] [-t]
                    [--scale SCALE] [-v] [--get-style]

  Railroad diagram generator

  optional arguments:
    -h, --help            show this help message and exit
    -i INPUT, --input INPUT
                          Diagram spec file
    -o OUTPUT, --output OUTPUT
                          Output file
    -s STYLES, --style STYLES
                          Style config file
    --title TITLE         Diagram title
    -t, --transparent     Transparent background
    --scale SCALE         Scale image
    -v, --version         Syntrax version
    --get-style           Create default style .ini

Any argument not associated with a flag is assumed to be the input file name. The default output format is PNG.

.. parsed-literal::

  > syntrax foo.spec
  Rendering to foo.png using cairo backend

You can specify the specific out file you want with the ``-o`` option. The extension determines the format. You can also pass just the extension to ``-o`` and Syntrax will use the input file base name for the output image:

.. parsed-literal::

  > syntrax -i foo.spec -o bar.pdf
  Rendering to bar.pdf using cairo backend


  > syntrax -i foo.spec -o eps
  Rendering to foo.eps using cairo backend


By default the images have a white background. If you want a transparent background pass the ``-t`` option.

You can control the scale of the resulting image with the ``--scale`` option. It takes a floating point scale factor. This is most useful for the PNG output.

Specification language
----------------------

Syntrax diagrams are created using a Python-based specification language. A series of nestable function calls generate specific diagram elements. Nodes in the diagram are represented by quoted strings. Nodes default to rounded bubbles but will change to a box when prefixed with "/". Note that this is the reverse of how the original SQLite generator works. The rounded bubbles are typically used for literal tokens. Boxes are typically place holders for FIXME.

The following functions are available for creating diagrams:

========= ============= ============
line()    loop()        toploop()
choice()  opt()         optx()
stack()   indentstack() rightstack()
========= ============= ============


line
~~~~

A ``line()`` creates a series of nodes arranged horizontally from left to right.

.. code-block:: python

  line('[', 'foo', ',', '/bar', ']')


.. image:: images/syntax_line.png

loop
~~~~

A ``loop()`` represents a repeatable section of the syntax diagram. It takes two arguments. The first is the line of nodes for the forward path and the second is the nodes for the backward path. The backward path is rendered with nodes ordered from right to left.

.. code-block:: python

  loop(line('/forward', 'path'), line('backward', 'path'))


.. image:: images/syntax_loop.png

Either the forward or backward path can be ``None`` to represent no nodes on that portion of the loop.

.. code-block:: python

  loop('forward', None)


.. image:: images/syntax_loop_none.png


toploop
~~~~~~~

A ``toploop()`` is a variant of ``loop()`` that places the backward path above the forward path.

.. code-block:: python

  toploop(line('(', 'forward', ')'), line(')', 'backward', '('))

.. image:: images/syntax_toploop.png


choice
~~~~~~

The ``choice()`` element represents a branch between multiple syntax options.

.. code-block:: python

  choice('A', 'B', 'C')

.. image:: images/syntax_choice.png


opt
~~~

An ``opt()`` element specifies an optional portion of the syntax. The main path bypasses the optional portion positioned below.

.. code-block:: python

  opt('A', 'B', 'C')

.. image:: images/syntax_opt.png

``opt()`` is a special case of the ``choice()`` function where the first choice is ``None`` and the remaining nodes are put into a single line for the second choice. The example above is equivalent the following:

.. code-block:: python

  choice(None, line('A', 'B', 'C'))

optx
~~~~

The ``optx()`` element is a variant of ``opt()`` with the main path passing through the nodes.

.. code-block:: python

  optx('A', 'B', 'C')

.. image:: images/syntax_optx.png

stack
~~~~~

The elements described above will concatenate indefinitely from left to right. To break up long sections of a diagram you use the ``stack()`` element. Each of its arguments forms a separate line that is stacked from top to bottom.

.. code-block:: python

  stack(
    line('top', 'line'),
    line('bottom', 'line')
  )

.. image:: images/syntax_stack.png

When an inner element of a stack argument list is an ``opt()`` or an ``optx()`` it will be rendered with a special vertical bypass.

.. code-block:: python

  stack(
    line('A', 'B'),
    opt('bypass'),
    line('finish')
  )

.. image:: images/syntax_bypass.png

indentstack
~~~~~~~~~~~

For more control of the stacking you can use the ``indentstack()`` element. It shifts lower lines to the right relative to the top line of the stack. Its first argument is an integer specifing the amount of indentation.
For more control of the stacking you can use the ``indentstack()`` element. It shifts lower lines to the right relative to the top line of the stack. Its first argument is an integer specifing the amount of indentation.

.. code-block:: python

  indentstack(3,
    line('top', 'line'),
    line('bottom', 'line')
  )

.. image:: images/syntax_indentstack.png

rightstack
~~~~~~~~~~

.. code-block:: python

  rightstack(
    line('top', 'line', 'with', 'more', 'code'),
    line('bottom', 'line')
  )

.. image:: images/syntax_rightstack.png

INI configuration
-----------------

You can control the styling of the generated diagrams by passing in a style INI file with the ``-s`` option. By default Syntrax will look for a file names "syntrax.ini" in the current directory and use that if it exists.

.. parsed-literal::

  [style]
  line_width = 2
  bubble_width = 2
  padding = 5
  line_color = (0,0,0)
  arrows = True
  bullet_fill = 'white'        ; Requires optional webcolors package to be installed
  symbol_fill = '#B3E5FC'
  bubble_fill = (144,164,174)
  text_color = (0,0,0)
  shadow = True
  shadow_fill = (0,0,0,127)
  token_font = ['Helvetica', 16, 'bold']
  bubble_font = ['Helvetica', 14, 'bold']
  box_font = ['Times', 14, 'italic']

The style configuration file has a single section named "[style]". It contains the following keys:

  line_width


    Connecting line width in pixels. Default is 2.


  bubble_width


    Bubble outline width in pixels. Default is 2


  padding


    Additional padding around each edge of the image in pixels. Default is 5.


  line_color


    Color of the connecting lines and bubble outlines. Default is (0,0,0) Black.


  arrows


    Boolean used to control rendering of line arrows. Default is True.


  bullet_fill


    Fill color for small bullets at start and end of the diagram.


  symbol_fill


    Fill color for boxed nodes.


  bubble_fill


    Fill color for bubble nodes.


  text_color


    Color of all text.


  shadow


    Boolean controlling the rendering of bubble shadows. Default is False


  shadow_fill


    Fill color for shadows.

  token_font


    Font for bubble nodes of single character tokens.


  bubble_font


    Font for bubble nodes.


  box_font


    Font for boxed nodes.

  title_font


    Font for image title.

Colors
~~~~~~

The various keys controlling coloration can use a variety of color formats. The primary color representation is a 3 or 4-tuple representing RGB or RGBA channels. All channels are an integer ranging from 0 to 255. If you have the optional `webcolors <http://pypi.python.org/pypi/webcolors/>`_ package installed you can use color names as a value.

Fonts
~~~~~

Fonts are specified as a list of three items in the following order:

* Font family (Helvetica, Times, Courrier, etc.)
* Point size (12, 14, 16, etc.)
* Style ('normal', 'bold', 'italic')

.. parsed-literal::

  bubble_font = ['Helvetica', 14, 'bold']

Hyperlinked SVG
---------------



.. toctree::
   :maxdepth: 1
   :hidden:

Indices and tables
------------------

* :ref:`genindex`
* :ref:`search`

