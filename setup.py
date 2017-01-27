#!/usr/bin/env python
try:
    from setuptools import setup
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

import happysad

setup(name='happysad',
      version=happysad.__version__,
      description=happysad.__doc__,
      author=happysad.__author__,
      author_email='sdvillal@gmail.com',
      url='https://github.com/sdvillal/happysad',
      license=happysad.__license__,
      py_modules=['happysad'],
      platforms=['all'],
      classifiers=[
          'Intended Audience :: Developers',
          'License :: OSI Approved :: BSD-3-Clause',
          'Topic :: Software Development',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
      ])
