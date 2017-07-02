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

     # Build wheel for distribution
     python setup.py bdist_wheel --universal

     # Use twine to upload. This will prompt for username and password
     pip install twine
     twine upload --username erotemic --skip-existing dist/*

     # Check the url to make sure everything worked
     https://pypi.org/project/futures_actors/

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
    """
    python -c "import setup; print(setup.parse_description())"
    """
    from os.path import dirname, join, exists
    readme_fpath = join(dirname(__file__), 'README.md')
    print('readme_fpath = %r' % (readme_fpath,))
    # This breaks on pip install, so check that it exists.
    if exists(readme_fpath):
        # strip out markdown to make a clean readme for pypi
        textlines = []
        with open(readme_fpath, 'r') as f:
            capture = False
            for line in f.readlines():
                if '# Purpose' in line:
                    capture = True
                elif line.startswith('##'):
                    break
                elif capture:
                    textlines += [line]
        text = ''.join(textlines).strip()
        text = text.replace('\n\n', '_NLHACK_')
        text = text.replace('\n', ' ')
        text = text.replace('_NLHACK_', '\n\n')
        return text


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
