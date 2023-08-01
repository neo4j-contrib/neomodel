#!/usr/bin/env python
"""
.. _neomodel_install_labels:

``neomodel_install_labels``
---------------------------

::

    Usage: neomodel_install_labels [OPTIONS] [APPS]...
    
      Setup indexes and constraints on labels in Neo4j for your neomodel schema.
    
      APPS specifies python modules or files with neomodel schema declarations.
    
      If a connection URL is not specified, the tool will look up the environment
      variable NEO4J_BOLT_URL. If that environment variable is not set, the tool
      will attempt to connect to the default URL bolt://neo4j:neo4j@localhost:7687
    
    Options:
      --neo4j-bolt-url, --db TEXT  Neo4j server URL
      --help                       Show this message and exit.

"""
from __future__ import print_function

import sys
from importlib import import_module
from os import environ, path

from .. import db, install_all_labels
import click


def load_python_module_or_file(name):
    """
    Imports an existing python module or file into the current workspace.

    In both cases, *the resource must exist*.

    :param name: A string that refers either to a Python module or a source coe
                 file to load in the current workspace.
    :type name: str
    """
    # Is a file
    if name.lower().endswith(".py"):
        basedir = path.dirname(path.abspath(name))
        # Add base directory to pythonpath
        sys.path.append(basedir)
        module_name = path.basename(name)[:-3]

    else:  # A module
        # Add current directory to pythonpath
        sys.path.append(path.abspath(path.curdir))

        module_name = name

    if module_name.startswith("."):
        pkg = module_name.split(".")[1]
    else:
        pkg = None

    import_module(module_name, package=pkg)
    click.echo(f"Loaded {name}")

@click.command()
@click.argument("apps", type=str, nargs=-1)
@click.option("--neo4j-bolt-url", "--db", type=str, help="Neo4j server URL", default=lambda: environ.get("NEO4J_BOLT_URL", "bolt://neo4j:neo4j@localhost:7687"))
def neomodel_install_labels(apps, neo4j_bolt_url):
    """
    Setup indexes and constraints on labels in Neo4j for your neomodel schema.

    APPS specifies python modules or files with neomodel schema declarations.
    
    If a connection URL is not specified, the tool will look up the environment 
    variable NEO4J_BOLT_URL. If that environment variable is not set, the tool 
    will attempt to connect to the default URL bolt://neo4j:neo4j@localhost:7687
    """
    for app in apps:
        load_python_module_or_file(app)

    # Connect to override any code in the module that may be resetting the connection
    click.echo(f"Connecting to {neo4j_bolt_url}")

    db.set_connection(neo4j_bolt_url)

    install_all_labels()


if __name__ == "__main__":
    neomodel_install_labels()
