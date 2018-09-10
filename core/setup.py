#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This setup file is provisional. Use pip install -r requirements.txt

from setuptools import setup, find_packages
from core import constants

NAME = 'Akilang'
DESCRIPTION = 'A compiler for a simple language, built with Python and LLVM'
URL = 'https://github.com/syegulalp/Akilang'
EMAIL = 'serdar@genjipress.com'
AUTHOR = 'Serdar Yegulalp'
REQUIRES_PYTHON = '>=3.6.0'
VERSION = constants.VERSION

REQUIRED = [
    'llvmlite==0.24.0',
    'colorama',
    'termcolor'
]

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=find_packages(exclude=('tests',)),
    install_requires=REQUIRED,
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Compilers',
        'Programming Language :: Other',
    ],
)