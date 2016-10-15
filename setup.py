import ez_setup
ez_setup.use_setuptools()

from setuptools import setup

# Use README.rst for the long description
with open('README.rst') as fh:
    long_description = fh.read()
    
# Scan the script for the version string
version_file = 'syntrax.py'
version = None
with open(version_file) as fh:
    try:
        version = [line.split('=')[1].strip().strip("'") for line in fh if \
            line.startswith('__version__')][0]
    except IndexError:
        pass

if version is None:
    raise RuntimeError('Unable to find version string in file: {0}'.format(version_file))


setup(name='syntrax',
    version=version,
    author='Kevin Thibedeau',
    author_email='kevin.thibedeau@gmail.com',
    url='http://kevinpt.github.io/syntrax',
    download_url='http://kevinpt.github.io/syntrax',
    description='Railroad syntax diagram generator',
    long_description=long_description,
    platforms = ['Any'],
    install_requires = [],
    packages = [],
    py_modules = ['syntrax', 'ez_setup'],
    entry_points = {
        'console_scripts': ['syntrax = syntrax:main']
    },
    include_package_data = True,

    use_2to3 = True,
    
    keywords='Railroad syntax diagram generator',
    license='MIT',
    classifiers=['Development Status :: 5 - Production/Stable',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License'
        ]
    )

