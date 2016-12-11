#!/usr/bin/env python3
from distutils.core import setup

from cms import name, version


setup(
    name=name,
    version=version,
    description='a content management system that uses plain markdown files',
    license='MIT',
    author='Foster McLane',
    author_email='fkmclane@gmail.com',
    packages=['cms'],
    package_data={'cms': ['html/*.*']},
)
