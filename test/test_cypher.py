from neo4j.exceptions import ClientError as CypherError
from pandas import DataFrame, Series

from neomodel import StringProperty, StructuredNode
from neomodel.core import db
from neomodel.integration.pandas import to_dataframe, to_series


class User2(StructuredNode):
    name = StringProperty()
    email = StringProperty()


class User3(StructuredNode):
    name = StringProperty()
    email = StringProperty()


def test_cypher():
    """
    test result format is backward compatible with earlier versions of neomodel
    """

    jim = User2(email="jim1@test.com").save()
    data, meta = jim.cypher(
        f"MATCH (a) WHERE {db.get_id_method()}(a)=$self RETURN a.email"
    )
    assert data[0][0] == "jim1@test.com"
    assert "a.email" in meta

    data, meta = jim.cypher(
        f"""
            MATCH (a) WHERE {db.get_id_method()}(a)=$self
            MATCH (a)<-[:USER2]-(b)
            RETURN a, b, 3
        """
    )
    assert "a" in meta and "b" in meta


def test_cypher_syntax_error():
    jim = User2(email="jim1@test.com").save()
    try:
        jim.cypher(f"MATCH a WHERE {db.get_id_method()}(a)={{self}} RETURN xx")
    except CypherError as e:
        assert hasattr(e, "message")
        assert hasattr(e, "code")
    else:
        assert False, "CypherError not raised."


def test_pandas_dataframe_integration():
    jimla = User2(email="jimla@test.com", name="jimla").save()
    jimlo = User2(email="jimlo@test.com", name="jimlo").save()
    df = to_dataframe(
        db.cypher_query("MATCH (a:User2) RETURN a.name AS name, a.email AS email")
    )

    assert isinstance(df, DataFrame)
    assert df.shape == (2, 2)
    assert df["name"].tolist() == ["jimla", "jimlo"]

    # Also test passing an index and dtype to to_dataframe
    df = to_dataframe(
        db.cypher_query("MATCH (a:User2) RETURN a.name AS name, a.email AS email"),
        index=df["email"],
        dtype=str,
    )

    assert df.index.inferred_type == "string"


def test_pandas_series_integration():
    jimly = User3(email="jimly@test.com", name="jimly").save()
    series = to_series(db.cypher_query("MATCH (a:User3) RETURN a.name AS name"))

    assert isinstance(series, Series)
    assert series.shape == (1,)
    assert series.tolist() == ["jimly"]
