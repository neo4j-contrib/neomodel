from neomodel.sync_ import vectorfilter
from test._async_compat import mark_sync_test
from neomodel.sync_.vectorfilter import VectorFilter
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


@mark_sync_test
def test_base_vectorfilter():
    """
    Tests that the vectorquery is ran, node and score are returned. 
    """
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
