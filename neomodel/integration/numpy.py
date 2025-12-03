"""
Provides integration with `numpy <https://numpy.org/>`_.

.. note::
   This module requires numpy to be installed, and will raise a
   warning if this is not available.

Example:

    >>> from neomodel.async_ import db
    >>> from neomodel.integration.numpy import to_nparray
    >>> db.set_connection('bolt://neo4j:secret@localhost:7687')
    >>> df = to_nparray(db.cypher_query("MATCH (u:User) RETURN u.email AS email, u.name AS name"))
    >>> df
    array([['jimla@test.com', 'jimla'], ['jimlo@test.com', 'jimlo']])
"""


from typing import Any, Literal
from warnings import warn

try:
    # noinspection PyPackageRequirements
    from numpy import array as nparray
    from numpy import ndarray
except ImportError:
    warn(
        "The neomodel.integration.numpy module expects numpy to be installed "
        "but it does not appear to be available."
    )
    raise


def to_ndarray(
    query_results: tuple[list[list[Any]], list[str]],
    dtype: Any | None = None,
    order: Literal["K", "A", "C", "F"] = "K",
) -> ndarray:
    """Convert the results of a db.cypher_query call into a numpy array.
    Optionally, specify a datatype and/or an order for the columns.
    """
    results, _ = query_results
    return nparray(results, dtype=dtype, order=order)
