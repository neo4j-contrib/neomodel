"""
Provides a test case for issue 277 - "match() returns Traversal".

https://github.com/neo4j-contrib/neomodel/issues/277

RelationshipManager.match() is documented to return a NodeSet, but it used to
return a Traversal, which does not expose NodeSet methods such as get() /
first() / filter(). As of 7.0.0 it returns a NodeSet as documented.
"""

from test._async_compat import mark_async_test

from neomodel import (
    AsyncNodeSet,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    AsyncStructuredRel,
    StringProperty,
    UniqueIdProperty,
)


class Issue277Rel(AsyncStructuredRel):
    prop = StringProperty()


class Issue277Node(AsyncStructuredNode):
    identifier = UniqueIdProperty()
    name = StringProperty()

    connected_to = AsyncRelationshipTo("Issue277Node", "CONNECTED", model=Issue277Rel)


@mark_async_test
async def test_rel_match_returns_node_set():
    a = await Issue277Node(name="a").save()

    assert type(a.connected_to.match(prop="asdf")) is AsyncNodeSet


@mark_async_test
async def test_rel_match_result_exposes_node_set_api():
    a = await Issue277Node(name="a").save()
    b = await Issue277Node(name="b").save()
    await a.connected_to.connect(b, {"prop": "hello"})

    # match() now returns a NodeSet, so the NodeSet API is available for
    # chaining - this used to raise AttributeError on a Traversal.
    result = a.connected_to.match(prop="hello")
    assert type(result) is AsyncNodeSet

    fetched = await result.get(name="b")
    assert fetched.name == "b"

    assert len(await a.connected_to.match(prop="hello")) == 1
    assert len(await a.connected_to.match(prop="nope")) == 0
