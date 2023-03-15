from typing import Sequence

from neomodel import db


def get_db_indexes_as_dict() -> Sequence[dict]:
    """Returns all indexes existing in the database

    Returns:
        Sequence[dict]: List of dictionaries, each entry being an index definition
    """
    indexes, meta_indexes = db.cypher_query("SHOW INDEXES")
    indexes_as_dict = [dict(zip(meta_indexes, row)) for row in indexes]

    return indexes_as_dict


def get_db_constraints_as_dict() -> Sequence[dict]:
    """Returns all constraints existing in the database

    Returns:
        Sequence[dict]: List of dictionaries, each entry being a constraint definition
    """
    constraints, meta_constraints = db.cypher_query("SHOW CONSTRAINTS")
    constraints_as_dict = [dict(zip(meta_constraints, row)) for row in constraints]

    return constraints_as_dict
