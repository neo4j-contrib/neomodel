#!/usr/bin/env python
"""
.. _neomodel_remove_labels:
    
``neomodel_remove_labels``
--------------------------

::

    Usage: neomodel_remove_labels [OPTIONS]
    
      Drop all indexes and constraints on labels from schema in Neo4j database.
    
      If a connection URL is not specified, the tool will look up the environment
      variable NEO4J_BOLT_URL. If that environment variable is not set, the tool
      will attempt to connect to the default URL bolt://neo4j:neo4j@localhost:7687
    
    Options:
      --neo4j-bolt-url, --db TEXT  Neo4j server URL
      --help                       Show this message and exit.

"""
from __future__ import print_function
from os import environ
from .. import db, remove_all_labels
import click

@click.command()
@click.option("--neo4j-bolt-url", "--db", type=str, help="Neo4j server URL", default=lambda: environ.get("NEO4J_BOLT_URL", "bolt://neo4j:neo4j@localhost:7687"))
def neomodel_remove_labels(neo4j_bolt_url):
    """
    Drop all indexes and constraints on labels from schema in Neo4j database.
    
    If a connection URL is not specified, the tool will look up the environment 
    variable NEO4J_BOLT_URL. If that environment variable is not set, the tool 
    will attempt to connect to the default URL bolt://neo4j:neo4j@localhost:7687
    """  
    # Connect to override any code in the module that may be resetting the connection
    click.echo(f"Connecting to {neo4j_bolt_url}\n")
    db.set_connection(neo4j_bolt_url)

    remove_all_labels()


if __name__ == "__main__":
    neomodel_remove_labels()
