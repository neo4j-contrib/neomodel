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

    Note : this script only has a synchronous mode.
    
    positional arguments:
      <someapp.models/app.py>
                            python modules or files with neomodel schema declarations.
    
    options:
      -h, --help            show this help message and exit
      --db bolt://neo4j:neo4j@localhost:7687
                            Neo4j Server URL
"""

import textwrap
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from os import environ

from neomodel.scripts.utils import load_python_module_or_file
from neomodel.sync_.core import db


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

    db.install_all_labels()


if __name__ == "__main__":
    main()
