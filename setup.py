#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on March 31, 2020

Copyright Alpes Lasers SA, Neuchatel, Switzerland, 2020

@author: chiesa
"""

from setuptools import setup

setup(
    setup_requires=['pbr'],
    pbr=True,
    test_suite = "stools.tests"
)