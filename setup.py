#!/usr/bin/env python

from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install
from subprocess import check_call

import djangoql


def download_completion_widget():
    # TODO: use some versioning mechanism
    # instead of pulling from the master branch
    base_url = 'https://github.com/ivelum/djangoql-completion/raw/main/dist/'
    target_folder = 'djangoql/static/djangoql/js/'
    files = [
        'completion.js',
        'completion.js.map',
    ]
    # Not using urllib b/c Python won't have SSL certificates on all platforms
    for file in files:
        check_call(['curl', '-L', base_url + file, '-o', target_folder + file])


class PreDevelopCommand(develop):
    def run(self):
        download_completion_widget()
        develop.run(self)


class PreInstallCommand(install):
    def run(self):
        download_completion_widget()
        install.run(self)


packages = ['djangoql']
requires = ['ply>=3.8']

setup(
    name='djangoql',
    version=djangoql.__version__,
    description='DjangoQL: Advanced search language for Django',
    long_description=open('README.rst').read(),
    long_description_content_type='text/x-rst',
    author='Denis Stebunov',
    author_email='support@ivelum.com',
    url='https://github.com/ivelum/djangoql/',
    packages=packages,
    include_package_data=True,
    install_requires=requires,
    license=open('LICENSE').readline().strip(),
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    cmdclass={
        'develop': PreDevelopCommand,
        'install': PreInstallCommand,
    },
)
