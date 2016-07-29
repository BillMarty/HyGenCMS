# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, July 2016

from distutils.core import setup

setup(name='HyGenCMS',
      version='0.1.0',
      py_modules=['adc',
                  'analogclient',
                  'asynciothread',
                  'bmsclient',
                  'config',
                  'deepseaclient',
                  'gpio',
                  'groveledbar',
                  'logfilewriter',
                  'main',
                  'pins',
                  'pwm',
                  'utils',
                  'woodwardcontrol',
                  ]
      )
