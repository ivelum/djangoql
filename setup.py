#!/usr/bin/env python

import os
import djangoql

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

packages = ['djangoql']
requires = ['ply>=3.8']

setup(
    name='djangoql',
    version=djangoql.__version__,
    description='DjangoQL: query mini-language that translates to Django ORM',
    long_description=open('README.rst').read(),
    author='Denis Stebunov',
    author_email='support@ivelum.com',
    url='https://github.com/ivelum/djangoql/',
    packages=packages,
    install_requires=requires,
    license=open('LICENSE').read(),
    zip_safe=False,
    classifiers=(
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ),
)

del os.environ['PYTHONDONTWRITEBYTECODE']
