#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Installation:
    pip install git+https://github.com/Erotemic/futures_actors.git

Developing:
    git clone https://github.com/Erotemic/futures_actors.git
    pip install -e futures_actors

Pypi:
     # First tag the source-code
     VERSION=$(python -c "import setup; print(setup.version)")
     echo $VERSION
     git tag $VERSION -m "tarball tag $VERSION"
     git push --tags origin master

     # Register on Pypi test
     python setup.py register -r pypitest
     python setup.py sdist upload -r pypitest

     # Check the url to make sure everything worked
     https://testpypi.python.org/pypi?:action=display&name=futures_actors

     # Register on Pypi live
     python setup.py register -r pypi
     # Note you need to temporarily edit your ~/.pypirc to include a password
     python setup.py sdist upload -r pypi

     # Check the url to make sure everything worked
     https://pypi.python.org/pypi?:action=display&name=futures_actors
"""
from setuptools import setup


def parse_version():
    """ Statically parse the version number from __init__.py """
    from os.path import dirname, join
    import ast
    init_fpath = join(dirname(__file__), 'futures_actors', '__init__.py')
    with open(init_fpath) as file_:
        sourcecode = file_.read()
    pt = ast.parse(sourcecode)
    class VersionVisitor(ast.NodeVisitor):
        def visit_Assign(self, node):
            for target in node.targets:
                if target.id == '__version__':
                    self.version = node.value.s
    visitor = VersionVisitor()
    visitor.visit(pt)
    return visitor.version


def parse_description():
    from os.path import dirname, join
    readme_fpath = join(dirname(__file__), 'README.md')
    with open(readme_fpath, 'r') as f:
        # TODO: strip out markdown to make a clean readme for pypi
        return f.read()


version = parse_version()


if __name__ == '__main__':
    setup(
        name='futures_actors',
        version=version,
        author='Jon Crall',
        install_requires=[
            'futures',
            # 'ubelt',
        ],
        author_email='erotemic@gmail.com',
        url='https://github.com/Erotemic/futures_actors',
        license='Apache 2',
        packages=['futures_actors'],
        classifiers=[
            # List of classifiers available at:
            # https://pypi.python.org/pypi?%3Aaction=list_classifiers
            'Development Status :: 3 - Alpha',
            'Intended Audience :: Developers',
            'Topic :: Software Development :: Libraries :: Python Modules',
            # This should be interpreted as Apache License v2.0
            'License :: OSI Approved :: Apache Software License',
            # Supported Python versions
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
        ],
    )
