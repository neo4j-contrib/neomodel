"""
Provides integration with `numpy <https://numpy.org/>`_.

.. note::
   This module requires numpy to be installed, and will raise a
   warning if this is not available.

Example:

    >>> from neomodel import db
    >>> from neomodel.integration.numpy import to_nparray
    >>> db.set_connection('bolt://neo4j:secret@localhost:7687')
    >>> df = to_nparray(db.cypher_query("MATCH (u:User) RETURN u.email AS email, u.name AS name"))
    >>> df
    array([['jimla@test.com', 'jimla'], ['jimlo@test.com', 'jimlo']])
"""


from warnings import warn

try:
    # noinspection PyPackageRequirements
    from numpy import array as nparray
except ImportError:
    warn(
        "The neomodel.integration.numpy module expects numpy to be installed "
        "but it does not appear to be available."
    )
    raise


def to_ndarray(query_results: tuple, dtype=None, order="K"):
    """Convert the results of a db.cypher_query call into a numpy array.
    Optionally, specify a datatype and/or an order for the columns.
    """
    results, _ = query_results
    return nparray(results, dtype=dtype, order=order)
