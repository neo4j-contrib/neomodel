from test._async_compat import mark_sync_test

from neomodel import (
    StructuredNode,
    VectorIndex,
    StringProperty,
    ArrayProperty,
    FloatProperty
    )

class someNode(StructuredNode):
    name = StringProperty()
    vector = ArrayProperty(base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine"))

class otherNode(StructuredNode):
    otherName = StringProperty() 
    other_vector = ArrayProperty(base_property=FloatProperty(), vector_index=VectorIndex(2, "cosine"))


@mark_sync_test
def test_vectorfilter():
    """
    Tests that the vectorquery is ran, node and score are returned. 
    """
    john = someNode(name="John", vector=[float(0.5), float(0.5)]).save()
    fred = someNode(name="Fred", vector=[float(1.0), float(0.0)]).save()
    james = otherNode(name="James", other_vector=[float(0.3), float(0.2)]).save()
    timothy = otherNode(name="Timothy", other_vector=[float(0.3), float(0.7)]).save()




