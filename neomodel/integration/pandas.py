"""
Provides integration with `pandas <https://pandas.pydata.org/>`_.

.. note::
   This module requires pandas to be installed, and will raise a
   warning if this is not available.

Example:

    >>> from neomodel import db
    >>> from neomodel.integration.pandas import to_dataframe
    >>> db.set_connection('bolt://neo4j:secret@localhost:7687')
    >>> df = to_dataframe(db.cypher_query("MATCH (u:User) RETURN u.email AS email, u.name AS name"))
    >>> df
                       email    name
    0         jimla@test.com   jimla
    1         jimlo@test.com   jimlo

    [2 rows x 2 columns]

"""


from warnings import warn

try:
    # noinspection PyPackageRequirements
    from pandas import DataFrame, Series
except ImportError:
    warn(
        "The neomodel.integration.pandas module expects pandas to be installed "
        "but it does not appear to be available."
    )
    raise


def to_dataframe(query_results: tuple, index=None, dtype=None):
    """Convert the results of a db.cypher_query call and associated metadata
    into a pandas DataFrame.
    Optionally, specify an index and/or a datatype for the columns.
    """
    results, meta = query_results
    return DataFrame(results, columns=meta, index=index, dtype=dtype)


def to_series(query_results: tuple, field=0, index=None, dtype=None):
    """Convert the results of a db.cypher_query call
    into a pandas Series for the given field.
    Optionally, specify an index and/or a datatype for the columns.
    """
    results, _ = query_results
    return Series([record[field] for record in results], index=index, dtype=dtype)
