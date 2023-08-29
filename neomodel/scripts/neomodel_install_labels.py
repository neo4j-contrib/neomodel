#!/usr/bin/env python
"""
.. _neomodel_install_labels:

``neomodel_install_labels``
---------------------------

::

    usage: neomodel_install_labels [-h] [--db bolt://neo4j:neo4j@localhost:7687] <someapp.models/app.py> [<someapp.models/app.py> ...]
    
    Setup indexes and constraints on labels in Neo4j for your neomodel schema.
    
    If a connection URL is not specified, the tool will look up the environment 
    variable NEO4J_BOLT_URL. If that environment variable is not set, the tool
    will attempt to connect to the default URL bolt://neo4j:neo4j@localhost:7687
    
    positional arguments:
      <someapp.models/app.py>
                            python modules or files with neomodel schema declarations.
    
    options:
      -h, --help            show this help message and exit
      --db bolt://neo4j:neo4j@localhost:7687
                            Neo4j Server URL
"""
from __future__ import print_function

import sys
import textwrap
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from importlib import import_module
from os import environ, path

from .. import db, install_all_labels


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
    print(f"Loaded {name}")


def main():
    parser = ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """
                                    Setup indexes and constraints on labels in Neo4j for your neomodel schema.

                                    If a connection URL is not specified, the tool will look up the environment 
                                    variable NEO4J_BOLT_URL. If that environment variable is not set, the tool
                                    will attempt to connect to the default URL bolt://neo4j:neo4j@localhost:7687
                                    """
        ),
    )

    parser.add_argument(
        "apps",
        metavar="<someapp.models/app.py>",
        type=str,
        nargs="+",
        help="python modules or files with neomodel schema declarations.",
    )

    parser.add_argument(
        "--db",
        metavar="bolt://neo4j:neo4j@localhost:7687",
        dest="neo4j_bolt_url",
        type=str,
        default="",
        help="Neo4j Server URL",
    )

    args = parser.parse_args()

    bolt_url = args.neo4j_bolt_url
    if len(bolt_url) == 0:
        bolt_url = environ.get("NEO4J_BOLT_URL", "bolt://neo4j:neo4j@localhost:7687")

    for app in args.apps:
        load_python_module_or_file(app)

    # Connect after to override any code in the module that may set the connection
    print(f"Connecting to {bolt_url}")
    db.set_connection(url=bolt_url)

    install_all_labels()


if __name__ == "__main__":
    main()
