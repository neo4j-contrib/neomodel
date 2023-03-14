#!/usr/bin/env python
from __future__ import print_function
from os import path, environ
import sys
from importlib import import_module
from argparse import ArgumentParser

from neomodel import db, install_all_labels


def load_python_module_or_file(name):
    # Is a file
    if name.lower().endswith('.py'):
        basedir = path.dirname(path.abspath(name))
        # Add base directory to pythonpath
        sys.path.append(basedir)
        module_name = path.basename(name)[:-3]

    else:  # A module
        # Add current directory to pythonpath
        sys.path.append(path.abspath(path.curdir))

        module_name = name

    if module_name.startswith('.'):
        pkg = module_name.split('.')[1]
    else:
        pkg = None

    import_module(module_name, package=pkg)
    print("Loaded {}.".format(name))


def main():
    parser = ArgumentParser(
        description='''
        Setup indexes and constraints on labels in Neo4j for your neomodel schema.

        Database credentials can be set by the environment variable NEO4J_BOLT_URL.
        ''')

    parser.add_argument(
        'apps',  metavar='<someapp.models/app.py>', type=str, nargs='+',
        help='python modules or files to load schema from.')

    parser.add_argument(
        '--db', metavar='bolt://neo4j:neo4j@localhost:7687', dest='neo4j_bolt_url', type=str, default='',
        help='address of your neo4j database'
    )

    args = parser.parse_args()

    bolt_url = args.neo4j_bolt_url
    if len(bolt_url) == 0:
        bolt_url = environ.get('NEO4J_BOLT_URL', 'bolt://neo4j:neo4j@localhost:7687')

    for app in args.apps:
        load_python_module_or_file(app)

    # Connect after to override any code in the module that may set the connection
    print('Connecting to {}\n'.format(bolt_url))
    db.set_connection(bolt_url)

    install_all_labels()

if __name__ == '__main__':
    main()
