#!/usr/bin/env python
from __future__ import print_function
from os import environ
from argparse import ArgumentParser

from neomodel import db, remove_all_labels


def main():
    parser = ArgumentParser(
        description='''
        Drop all indexes and constraints on labels from schema in Neo4j database.

        Database credentials can be set by the environment variable NEO4J_BOLT_URL.
        ''')

    parser.add_argument(
        '--db', metavar='bolt://neo4j:neo4j@localhost:7687', dest='neo4j_bolt_url', type=str, default='',
        help='address of your neo4j database'
    )

    args = parser.parse_args()

    bolt_url = args.neo4j_bolt_url
    if len(bolt_url) == 0:
        bolt_url = environ.get('NEO4J_BOLT_URL', 'bolt://neo4j:neo4j@localhost:7687')

    # Connect after to override any code in the module that may set the connection
    print('Connecting to {}\n'.format(bolt_url))
    db.set_connection(bolt_url)

    remove_all_labels()

if __name__ == '__main__':
    main()
