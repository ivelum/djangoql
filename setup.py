#!/usr/bin/env python

from subprocess import check_call

from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install

import djangoql


def download_completion_widget():
    src_base = 'https://github.com/ivelum/djangoql-completion/raw/0.3.2/dist/'
    target_base = 'djangoql/static/djangoql/'
    files = {
        'completion.js': target_base + 'js/',
        'completion.js.map': target_base + 'js/',
        'completion.css': target_base + 'css/',
    }
    # Not using urllib b/c Python won't have SSL certificates on all platforms
    for file, target_dir in files.items():
        check_call(['curl', '-fL', src_base + file, '-o', target_dir + file])


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
