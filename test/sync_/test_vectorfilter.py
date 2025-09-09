from test._async_compat import mark_sync_test
from test.conftest import check_and_skip_neo4j_least_version
from neomodel.semantic_filters import VectorFilter
from neomodel import (
    StructuredNode,
    VectorIndex,
    StringProperty,
    ArrayProperty,
    FloatProperty
    )

from neomodel.sync_.core import install_all_labels, remove_all_labels

class someNode(StructuredNode):
    name = StringProperty()
    vector = ArrayProperty(base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine"))

class otherNode(StructuredNode):
    otherName = StringProperty() 
    other_vector = ArrayProperty(base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine"))

class djangoNode(StructuredNode):
    name = StringProperty()
    vector = ArrayProperty(base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine"))
    number = FloatProperty()

@mark_sync_test
def test_base_vectorfilter():
    """
    Tests that the vectorquery is ran, node and score are returned. 
    """

    # Vector Indexes only exist from 5.13 onwards
    check_and_skip_neo4j_least_version(required_least_neo4j_version=50103, 
                                       message="Vector Index not Generally Available in Neo4j.")

    john = someNode(name="John", vector=[float(0.5), float(0.5)]).save()
    fred = someNode(name="Fred", vector=[float(1.0), float(0.0)]).save()
    
    install_all_labels()

    someNodeSearch = someNode.nodes.filter(vector_filter=VectorFilter(topk=3, vector_attribute_name="vector", candidate_vector=[0.25, 0]))
    result = someNodeSearch.all()
    assert all(isinstance(x[0], someNode) for x in result)
    assert all(isinstance(x[1], float) for x in result)

    remove_all_labels()

@mark_sync_test
def test_vectorfilter_with_node_propertyfilter():
    """
    Tests that the vector query is ran, and "john" node is the only node returned
    """

    # Vector Indexes only exist from 5.13 onwards
    check_and_skip_neo4j_least_version(required_least_neo4j_version=50103, 
                                       message="Vector Index not Generally Available in Neo4j.")

    john = someNode(name="John", vector=[float(0.5), float(0.5)]).save()
    fred = someNode(name="Fred", vector=[float(1.0), float(0.0)]).save()

    install_all_labels()

    vectorsearchFilterforJohn = someNode.nodes.filter(vector_filter=VectorFilter(topk=3, vector_attribute_name="vector", candidate_vector=[0.25, 0]), name="John")
    result = vectorsearchFilterforJohn.all()

    assert len(result) == 1
    assert all(isinstance(x[0], someNode) for x in result)
    assert result[0][0].name == "John"
    assert all(isinstance(x[1], float) for x in result)
    
    remove_all_labels()

@mark_sync_test
def test_dont_duplicate_vector_filter_node():
    """
    Tests the situation that another node have the same filter value.
    Testing that we are only perfomring the vectorfilter and metadata filter on the right nodes. 
    """

    # Vector Indexes only exist from 5.13 onwards
    check_and_skip_neo4j_least_version(required_least_neo4j_version=50103, 
                                       message="Vector Index not Generally Available in Neo4j.")

    john = someNode(name="John", vector=[float(0.5), float(0.5)]).save()
    fred = someNode(name="Fred", vector=[float(1.0), float(0.0)]).save()
    john2 = otherNode(name="John", vector=[float(0.5), float(0.1)]).save()
    fred2 = otherNode(name="Fred", vector=[float(0.9), float(0.2)]).save()

    install_all_labels()
    
    john_vector_search = someNode.nodes.filter(vector_filter=VectorFilter(topk=3, vector_attribute_name="vector", candidate_vector=[0.25,0]), name="John")
    result = john_vector_search.all()

    assert len(result) == 1 # Check we only get the one John
    assert isinstance(result[0][0], someNode) # check we only get the someNode John
    assert result[0][0].name == "John"
    assert isinstance(result[0][1], float)

    remove_all_labels()

@mark_sync_test
def test_django_filter_w_vector_filter():
    """
    Tests that django filters still work with the vector filter on.
    """

    # Vector Indexes only exist from 5.13 onwards
    check_and_skip_neo4j_least_version(required_least_neo4j_version=50103, 
                                       message="Vector Index not Generally Available in Neo4j.")

    nodeone = djangoNode(name="John", vector=[float(0.5), float(0.5)], number=float(10)).save()
    nodetwo = djangoNode(name="Fred", vector=[float(0.8), float(0.5)], number=float(3)).save()

    install_all_labels()
    vector_search_with_django_filter = djangoNode.nodes.filter(vector_filter=VectorFilter(topk=10, vector_attribute_name="vector", candidate_vector=[0.25, 0.25]), number__gt=5)
    result = vector_search_with_django_filter.all()
    assert len(result) == 1 # we only get the one node
    assert isinstance(result[0][0], djangoNode)
    assert result[0][0].number > 5 

    remove_all_labels()



