# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

from os import path

from setuptools import setup, find_packages

import hygencms

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='HyGenCMS',
    version=hygencms.__version__,

    description='Control and logging for the HyGen',
    long_description=long_description,

    # Author details
    author='Matthew West',
    author_email='mwest@planetarypower.com',

    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Planetary Power',

        # Versions of python supported
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],

    packages=find_packages(exclude=['docs', 'tests']),

    install_requires=['modbus_tk',
                      'pyserial',
                      'python-daemon',
                      'recordclass',
                      'monotonic'],

    entry_points={
        'console_scripts': [
            'hygencms = hygencms.__main__:main'
        ]
    },

    package_data={
        'hygencms': ['*.csv'],
    },
)
