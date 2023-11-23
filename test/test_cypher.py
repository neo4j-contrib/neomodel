import builtins

import pytest
from neo4j.exceptions import ClientError as CypherError
from numpy import ndarray
from pandas import DataFrame, Series

from neomodel import StringProperty, StructuredNodeAsync
from neomodel._async.core import adb


class User2(StructuredNodeAsync):
    name = StringProperty()
    email = StringProperty()


class UserPandas(StructuredNodeAsync):
    name = StringProperty()
    email = StringProperty()


class UserNP(StructuredNodeAsync):
    name = StringProperty()
    email = StringProperty()


@pytest.fixture
def hide_available_pkg(monkeypatch, request):
    import_orig = builtins.__import__

    def mocked_import(name, *args, **kwargs):
        if name == request.param:
            raise ImportError()
        return import_orig(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mocked_import)


@pytest.mark.asyncio
async def test_cypher_async():
    """
    test result format is backward compatible with earlier versions of neomodel
    """

    jim = await User2(email="jim1@test.com").save_async()
    data, meta = await jim.cypher_async(
        f"MATCH (a) WHERE {adb.get_id_method()}(a)=$self RETURN a.email"
    )
    assert data[0][0] == "jim1@test.com"
    assert "a.email" in meta

    data, meta = await jim.cypher_async(
        f"""
            MATCH (a) WHERE {adb.get_id_method()}(a)=$self
            MATCH (a)<-[:USER2]-(b)
            RETURN a, b, 3
        """
    )
    assert "a" in meta and "b" in meta


@pytest.mark.asyncio
async def test_cypher_syntax_error_async():
    jim = await User2(email="jim1@test.com").save_async()
    try:
        await jim.cypher_async(
            f"MATCH a WHERE {adb.get_id_method()}(a)={{self}} RETURN xx"
        )
    except CypherError as e:
        assert hasattr(e, "message")
        assert hasattr(e, "code")
    else:
        assert False, "CypherError not raised."


@pytest.mark.asyncio
@pytest.mark.parametrize("hide_available_pkg", ["pandas"], indirect=True)
async def test_pandas_not_installed_async(hide_available_pkg):
    with pytest.raises(ImportError):
        with pytest.warns(
            UserWarning,
            match="The neomodel.integration.pandas module expects pandas to be installed",
        ):
            from neomodel.integration.pandas import to_dataframe

            _ = to_dataframe(
                await adb.cypher_query_async("MATCH (a) RETURN a.name AS name")
            )


@pytest.mark.asyncio
async def test_pandas_integration_async():
    from neomodel.integration.pandas import to_dataframe, to_series

    jimla = await UserPandas(email="jimla@test.com", name="jimla").save_async()
    jimlo = await UserPandas(email="jimlo@test.com", name="jimlo").save_async()

    # Test to_dataframe
    df = to_dataframe(
        await adb.cypher_query_async(
            "MATCH (a:UserPandas) RETURN a.name AS name, a.email AS email"
        )
    )

    assert isinstance(df, DataFrame)
    assert df.shape == (2, 2)
    assert df["name"].tolist() == ["jimla", "jimlo"]

    # Also test passing an index and dtype to to_dataframe
    df = to_dataframe(
        await adb.cypher_query_async(
            "MATCH (a:UserPandas) RETURN a.name AS name, a.email AS email"
        ),
        index=df["email"],
        dtype=str,
    )

    assert df.index.inferred_type == "string"

    # Next test to_series
    series = to_series(
        await adb.cypher_query_async("MATCH (a:UserPandas) RETURN a.name AS name")
    )

    assert isinstance(series, Series)
    assert series.shape == (2,)
    assert df["name"].tolist() == ["jimla", "jimlo"]


@pytest.mark.asyncio
@pytest.mark.parametrize("hide_available_pkg", ["numpy"], indirect=True)
async def test_numpy_not_installed_async(hide_available_pkg):
    with pytest.raises(ImportError):
        with pytest.warns(
            UserWarning,
            match="The neomodel.integration.numpy module expects pandas to be installed",
        ):
            from neomodel.integration.numpy import to_ndarray

            _ = to_ndarray(
                await adb.cypher_query_async("MATCH (a) RETURN a.name AS name")
            )


@pytest.mark.asyncio
async def test_numpy_integration_async():
    from neomodel.integration.numpy import to_ndarray

    jimly = await UserNP(email="jimly@test.com", name="jimly").save_async()
    jimlu = await UserNP(email="jimlu@test.com", name="jimlu").save_async()

    array = to_ndarray(
        await adb.cypher_query_async(
            "MATCH (a:UserNP) RETURN a.name AS name, a.email AS email"
        )
    )

    assert isinstance(array, ndarray)
    assert array.shape == (2, 2)
    assert array[0][0] == "jimly"
