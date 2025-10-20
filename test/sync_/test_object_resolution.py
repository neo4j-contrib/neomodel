"""
Test cases for object resolution with resolve_objects=True in raw Cypher queries.

This test file covers various scenarios for automatic class resolution,
including the issues identified in GitHub issues #905 and #906:
- Issue #905: Nested lists in results of raw Cypher queries with collect keyword
- Issue #906: Automatic class resolution for raw queries with nodes nested in maps

Additional scenarios tested:
- Basic object resolution
- Nested structures (lists, maps, mixed)
- Path resolution
- Relationship resolution
- Complex nested scenarios with collect() and other Cypher functions
"""

from test._async_compat import mark_sync_test

from neomodel import (
    IntegerProperty,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
    db,
)


class TestRelationship(StructuredRel):
    """Test relationship with properties."""

    weight = IntegerProperty(default=1)
    description = StringProperty(default="test")


class TestNode(StructuredNode):
    """Base test node class."""

    name = StringProperty(required=True)
    value = IntegerProperty(default=0)
    related = RelationshipTo("TestNode", "RELATED_TO", model=TestRelationship)


class SpecialNode(StructuredNode):
    """Specialized test node class."""

    name = StringProperty(required=True)
    special_value = IntegerProperty(default=42)
    related = RelationshipTo(TestNode, "RELATED_TO", model=TestRelationship)


class ContainerNode(StructuredNode):
    """Container node for testing nested structures."""

    name = StringProperty(required=True)
    items = RelationshipTo(TestNode, "CONTAINS", model=TestRelationship)


@mark_sync_test
def test_basic_object_resolution():
    """Test basic object resolution for nodes and relationships."""
    # Create test data
    TestNode(name="Node1", value=10).save()
    TestNode(name="Node2", value=20).save()

    # Test basic node resolution
    results, _ = db.cypher_query(
        "MATCH (n:TestNode) WHERE n.name = $name RETURN n",
        {"name": "Node1"},
        resolve_objects=True,
    )

    assert len(results) == 1
    assert len(results[0]) == 1
    resolved_node = results[0][0]
    assert isinstance(resolved_node, TestNode)
    assert resolved_node.name == "Node1"
    assert resolved_node.value == 10


@mark_sync_test
def test_relationship_resolution():
    """Test relationship resolution in queries."""
    # Create test data with relationships
    node1 = TestNode(name="Source", value=100).save()
    node2 = TestNode(name="Target", value=200).save()

    # Create relationship
    node1.related.connect(node2, {"weight": 5, "description": "test_rel"})

    # Test relationship resolution
    results, _ = db.cypher_query(
        "MATCH (a:TestNode)-[r:RELATED_TO]->(b:TestNode) RETURN a, r, b",
        resolve_objects=True,
    )

    assert len(results) == 1
    source, rel, target = results[0]

    assert isinstance(source, TestNode)
    assert isinstance(rel, TestRelationship)
    assert isinstance(target, TestNode)

    assert source.name == "Source"
    assert target.name == "Target"
    assert rel.weight == 5
    assert rel.description == "test_rel"


@mark_sync_test
def test_path_resolution():
    """Test path resolution in queries."""
    # Create test data
    node1 = TestNode(name="Start", value=1).save()
    node2 = TestNode(name="Middle", value=2).save()
    node3 = TestNode(name="End", value=3).save()

    # Create path
    node1.related.connect(node2, {"weight": 1})
    node2.related.connect(node3, {"weight": 2})

    # Test path resolution
    results, _ = db.cypher_query(
        "MATCH p=(a:TestNode)-[:RELATED_TO*2]->(c:TestNode) RETURN p",
        resolve_objects=True,
    )

    assert len(results) == 1
    path = results[0][0]

    # Path should be resolved to AsyncNeomodelPath
    from neomodel.sync_.path import NeomodelPath

    assert isinstance(path, NeomodelPath)
    assert len(path._nodes) == 3  # pylint: disable=protected-access
    assert len(path._relationships) == 2  # pylint: disable=protected-access


@mark_sync_test
def test_nested_lists_basic():
    """Test basic nested list resolution (Issue #905 - basic case)."""
    # Create test data
    nodes = []
    for i in range(3):
        node = TestNode(name=f"Node{i}", value=i * 10).save()
        nodes.append(node)

    # Test nested list resolution
    results, _ = db.cypher_query(
        "MATCH (n:TestNode) RETURN collect(n) as nodes", resolve_objects=True
    )

    assert len(results) == 1
    collected_nodes = results[0][0]

    assert isinstance(collected_nodes, list)
    assert len(collected_nodes) == 3

    for i, node in enumerate(collected_nodes):
        assert isinstance(node, TestNode)
        assert node.name == f"Node{i}"
        assert node.value == i * 10


@mark_sync_test
def test_nested_lists_complex():
    """Test complex nested list resolution with collect() (Issue #905 - complex case)."""
    # Create test data with relationships
    container = ContainerNode(name="Container").save()
    items = []
    for i in range(2):
        item = TestNode(name=f"Item{i}", value=i * 5).save()
        items.append(item)
        container.items.connect(item, {"weight": i + 1})

    # Test complex nested list with collect
    results, _ = db.cypher_query(
        """
        MATCH (c:ContainerNode)-[r:CONTAINS]->(i:TestNode)
        WITH c, collect({item: i, rel: r}) as items
        RETURN c, items
        """,
        resolve_objects=True,
    )

    assert len(results) == 1
    container_result, items_result = results[0]

    assert isinstance(container_result, ContainerNode)
    assert container_result.name == "Container"

    assert isinstance(items_result, list)
    assert len(items_result) == 2

    for i, item_data in enumerate(items_result):
        assert isinstance(item_data, dict)
        assert "item" in item_data
        assert "rel" in item_data

        item = item_data["item"]
        rel = item_data["rel"]

        assert isinstance(item, TestNode)
        assert isinstance(rel, TestRelationship)
        assert item.name == f"Item{i}"
        assert rel.weight == i + 1


@mark_sync_test
def test_nodes_nested_in_maps():
    """Test nodes nested in maps (Issue #906)."""
    # Create test data
    TestNode(name="Node1", value=100).save()
    TestNode(name="Node2", value=200).save()

    # Test nodes nested in maps
    results, _ = db.cypher_query(
        """
        MATCH (n1:TestNode), (n2:TestNode)
        WHERE n1.name = 'Node1' AND n2.name = 'Node2'
        RETURN {
            first: n1,
            second: n2,
            metadata: {
                count: 2,
                description: 'test map'
            }
        } as result_map
        """,
        resolve_objects=True,
    )

    assert len(results) == 1
    result_map = results[0][0]

    assert isinstance(result_map, dict)
    assert "first" in result_map
    assert "second" in result_map
    assert "metadata" in result_map

    # Check that nodes are properly resolved
    first_node = result_map["first"]
    second_node = result_map["second"]

    assert isinstance(first_node, TestNode)
    assert isinstance(second_node, TestNode)
    assert first_node.name == "Node1"
    assert second_node.name == "Node2"

    # Check metadata (should remain as primitive types)
    metadata = result_map["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["count"] == 2
    assert metadata["description"] == "test map"


@mark_sync_test
def test_mixed_nested_structures():
    """Test mixed nested structures with lists, maps, and nodes."""
    # Create test data
    special = SpecialNode(name="Special", special_value=999).save()
    test_nodes = []
    for i in range(2):
        node = TestNode(name=f"Test{i}", value=i * 100).save()
        test_nodes.append(node)
        special.related.connect(node, {"weight": i + 10})

    # Test complex mixed structure
    results, _ = db.cypher_query(
        """
        MATCH (s:SpecialNode)-[r:RELATED_TO]->(t:TestNode)
        WITH s, collect({node: t, rel: r}) as related_items
        RETURN {
            special_node: s,
            related: related_items,
            summary: {
                total_relations: size(related_items),
                node_names: [item in related_items | item.node.name]
            }
        } as complex_result
        """,
        resolve_objects=True,
    )

    assert len(results) == 1
    complex_result = results[0][0]

    assert isinstance(complex_result, dict)
    assert "special_node" in complex_result
    assert "related" in complex_result
    assert "summary" in complex_result

    # Check special node resolution
    special_node = complex_result["special_node"]
    assert isinstance(special_node, SpecialNode)
    assert special_node.name == "Special"
    assert special_node.special_value == 999

    # Check related items (list of dicts with nodes and relationships)
    related = complex_result["related"]
    assert isinstance(related, list)
    assert len(related) == 2

    for i, item in enumerate(related):
        assert isinstance(item, dict)
        assert "node" in item
        assert "rel" in item

        node = item["node"]
        rel = item["rel"]

        assert isinstance(node, TestNode)
        assert isinstance(rel, TestRelationship)
        assert node.name == f"Test{i}"
        assert rel.weight == i + 10

    # Check summary (should remain as primitive types)
    summary = complex_result["summary"]
    assert isinstance(summary, dict)
    assert summary["total_relations"] == 2
    assert isinstance(summary["node_names"], list)
    assert summary["node_names"] == ["Test0", "Test1"]


@mark_sync_test
def test_deeply_nested_structures():
    """Test deeply nested structures to ensure recursive resolution works."""
    # Create test data
    nodes = []
    for i in range(3):
        node = TestNode(name=f"Deep{i}", value=i * 50).save()
        nodes.append(node)

    # Test deeply nested structure
    results, _ = db.cypher_query(
        """
        MATCH (n:TestNode)
        WITH collect(n) as level1
        RETURN {
            level1: level1,
            level2: {
                nodes: level1,
                metadata: {
                    level3: {
                        count: size(level1),
                        items: level1
                    }
                }
            }
        } as deep_result
        """,
        resolve_objects=True,
    )

    assert len(results) == 1
    deep_result = results[0][0]

    assert isinstance(deep_result, dict)
    assert "level1" in deep_result
    assert "level2" in deep_result

    # Check level1 (direct list of nodes)
    level1 = deep_result["level1"]
    assert isinstance(level1, list)
    assert len(level1) == 3
    for i, node in enumerate(level1):
        assert isinstance(node, TestNode)
        assert node.name == f"Deep{i}"

    # Check level2 (nested structure)
    level2 = deep_result["level2"]
    assert isinstance(level2, dict)
    assert "nodes" in level2
    assert "metadata" in level2

    # Check nodes in level2
    level2_nodes = level2["nodes"]
    assert isinstance(level2_nodes, list)
    assert len(level2_nodes) == 3
    for i, node in enumerate(level2_nodes):
        assert isinstance(node, TestNode)
        assert node.name == f"Deep{i}"

    # Check metadata in level2
    metadata = level2["metadata"]
    assert isinstance(metadata, dict)
    assert "level3" in metadata

    level3 = metadata["level3"]
    assert isinstance(level3, dict)
    assert "count" in level3
    assert "items" in level3

    assert level3["count"] == 3
    level3_items = level3["items"]
    assert isinstance(level3_items, list)
    assert len(level3_items) == 3
    for i, node in enumerate(level3_items):
        assert isinstance(node, TestNode)
        assert node.name == f"Deep{i}"


@mark_sync_test
def test_collect_with_aggregation():
    """Test collect() with aggregation functions."""
    # Create test data
    for i in range(5):
        node = TestNode(name=f"AggNode{i}", value=i * 10).save()

    # Test collect with aggregation
    results, _ = db.cypher_query(
        """
        MATCH (n:TestNode)
        WHERE n.name STARTS WITH 'Agg'
        WITH collect(n) as all_nodes
        RETURN {
            nodes: all_nodes,
            count: size(all_nodes),
            total_value: reduce(total = 0, n in all_nodes | total + n.value),
            names: [n in all_nodes | n.name]
        } as aggregated_result
        """,
        resolve_objects=True,
    )

    assert len(results) == 1
    aggregated_result = results[0][0]

    assert isinstance(aggregated_result, dict)
    assert "nodes" in aggregated_result
    assert "count" in aggregated_result
    assert "total_value" in aggregated_result
    assert "names" in aggregated_result

    # Check nodes are resolved
    nodes = aggregated_result["nodes"]
    assert isinstance(nodes, list)
    assert len(nodes) == 5
    for i, node in enumerate(nodes):
        assert isinstance(node, TestNode)
        assert node.name == f"AggNode{i}"
        assert node.value == i * 10

    # Check aggregated values
    assert aggregated_result["count"] == 5
    assert aggregated_result["total_value"] == 100  # 0+10+20+30+40
    assert aggregated_result["names"] == [
        "AggNode0",
        "AggNode1",
        "AggNode2",
        "AggNode3",
        "AggNode4",
    ]


@mark_sync_test
def test_resolve_objects_false_comparison():
    """Test that resolve_objects=False returns raw Neo4j objects."""
    # Create test data
    TestNode(name="RawNode", value=123).save()

    # Test with resolve_objects=False
    results_false, _ = db.cypher_query(
        "MATCH (n:TestNode) WHERE n.name = $name RETURN n",
        {"name": "RawNode"},
        resolve_objects=False,
    )

    # Test with resolve_objects=True
    results_true, _ = db.cypher_query(
        "MATCH (n:TestNode) WHERE n.name = $name RETURN n",
        {"name": "RawNode"},
        resolve_objects=True,
    )

    # Compare results
    raw_node = results_false[0][0]
    resolved_node = results_true[0][0]

    # Raw node should be a Neo4j Node object
    from neo4j.graph import Node

    assert isinstance(raw_node, Node)
    assert raw_node["name"] == "RawNode"
    assert raw_node["value"] == 123

    # Resolved node should be a TestNode instance
    assert isinstance(resolved_node, TestNode)
    assert resolved_node.name == "RawNode"
    assert resolved_node.value == 123


@mark_sync_test
def test_empty_results():
    """Test object resolution with empty results."""
    # Test empty results
    results, _ = db.cypher_query(
        "MATCH (n:TestNode) WHERE n.name = 'NonExistent' RETURN n", resolve_objects=True
    )

    assert len(results) == 0


@mark_sync_test
def test_primitive_types_preserved():
    """Test that primitive types are preserved during object resolution."""
    # Create test data
    TestNode(name="PrimitiveTest", value=456).save()

    # Test with mixed primitive and node types
    results, _ = db.cypher_query(
        """
        MATCH (n:TestNode) WHERE n.name = $name
        RETURN n, n.value as int_val, n.name as str_val, true as bool_val, 3.14 as float_val
        """,
        {"name": "PrimitiveTest"},
        resolve_objects=True,
    )

    assert len(results) == 1
    node_result, int_val, str_val, bool_val, float_val = results[0]

    # Node should be resolved
    assert isinstance(node_result, TestNode)
    assert node_result.name == "PrimitiveTest"

    # Primitives should remain primitive
    assert isinstance(int_val, int)
    assert int_val == 456

    assert isinstance(str_val, str)
    assert str_val == "PrimitiveTest"

    assert isinstance(bool_val, bool)
    assert bool_val is True

    assert isinstance(float_val, float)
    assert float_val == 3.14
