.. _Semantic Indexes:

==================================
Semantic Indexes
==================================

Full Text Index
----------------
From version 6.0.0 neomodel provides a way to interact with neo4j `Full Text indexing <https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/full-text-indexes/>`_. 
The Full Text Index can be created for both node and relationship properties. Only available for Neo4j version 5.16 or higher.

Defining a Full Text Index on a Property
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Within neomodel, indexing is a decision that is made at class definition time as the index needs to be built. A Full Text index is defined using :class:`~neomodel.properties.FulltextIndex`
To define a property with a full text index we use the following syntax::
    
    StringProperty(fulltext_index=FulltextIndex(analyzer="standard-no-stop-words", eventually_consistent=False))

Where,
    - ``analyzer``: The analyzer to use. The default is ``standard-no-stop-words``.
    - ``eventually_consistent``: Whether the index should be eventually consistent. The default is ``False``.

The index must then be built, this occurs when the function :func:`~neomodel.sync_.core.install_all_labels` is run. 

Please refer to the `Neo4j documentation <https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/full-text-indexes/#configuration-settings>`_ for more information on fulltext indexes.

Querying a Full Text Index on a Property
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Node Property 
^^^^^^^^^^^^^
The following Fulltext Index property::

    class Product(StructuredNode):
            name = StringProperty()
            description = StringProperty(
                fulltext_index=FulltextIndex(
                    analyzer="standard-no-stop-words", eventually_consistent=False
                )
            )

Can be queried using :class:`~neomodel.semantic_filters.FulltextFilter`. Such as::

    from neomodel.semantic_filters import FulltextFilter
    result = Product.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=10,
            fulltext_attribute_name="description",
            query_string="product")).all()

Where the result will be a list of length topk of nodes with the form (ProductNode, score).

If you would like to filter the nodes based on a threshold (ie. nodes similarity >= threshold), you can use the following::

    from neomodel.semantic_filters import FulltextFilter
    result = Product.nodes.filter(
        fulltext_filter=FulltextFilter(
            topk=10,
            fulltext_attribute_name="description",
            query_string="product",
            threshold=0.08)).all()

Only nodes above threshold = 0.08 will be returned.

The :class:`~neomodel.semantic_filters.FulltextFilter` can be used in conjunction with the normal filter types.

.. attention:: 
    If you use FulltextFilter in conjunction with normal filter types, only nodes that fit the filters will return thus, you may get less than the topk specified.
    Furthermore, all node filters **should** work with FulltextFilter, relationship filters will also work but WILL NOT return the fulltext similarity score alongside the relationship filter, instead the topk nodes and their appropriate relationships will be returned.

RelationshipProperty
^^^^^^^^^^^^^^^^^^^^

Currently neomodel has not implemented an OGM method for querying full text indexes on relationships.
If this is something that you would like, please submit a GitHub issue with requirements highlighting your usage pattern. 

Alternatively, whilst this has not been implemented yet you can still leverage `db.cypher_query` with the correct syntax to perform your required query. 

Vector Index 
------------
From version 5.5.0 neomodel provides a way to interact with neo4j `vector indexing <https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/>`_.

The Vector Index can be created on both node and relationship properties. Only available for Neo4j version 5.15 (node) and 5.18 (relationship) or higher. 

Defining a Vector Index on a Property 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Within neomodel, indexing is a decision that is made at class definition time as the index needs to be built. A vector index is defined using :class:`~neomodel.properties.VectorIndex`.
To define a property with a vector index we use the following syntax::

    ArrayProperty(base_property=FloatProperty(), vector_index=VectorIndex(dimensions=512, similarity_function="cosine"))
    
Where,
    - ``dimensions``: The dimension of the vector. The default is 1536.
    - ``similarity_function``: The similarity algorithm to use. The default is ``cosine``.

The index must then be built, this occurs when the function :func:`~neomodel.sync_.core.install_all_labels` is run.

The vector indexes will then have the name "vector_index_{node.__label__}_{propertyname_with_vector_index}".

.. attention:: 
   Neomodel creates a new vector index for each specified property, thus you cannot have two distinct properties being placed into the same index. 

Querying a Vector Index on a Property 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Node Property
^^^^^^^^^^^^^
The following node vector index property::

    class someNode(StructuredNode):
        vector = ArrayProperty(base_property=FloatProperty(), vector_index=VectorIndex(dimensions=512, similarity_function="cosine"))
        name = StringProperty()

Can be queried using :class:`~neomodel.semantic_filters.VectorFilter`. Such as::

    from neomodel.semantic_filters import VectorFilter
    result = someNode.nodes.filter(
        vector_filter=VectorFilter(
            topk=3, 
            vector_attribute_name="vector", 
            candidate_vector=[0.25, 0.25])).all()

Where the result will be a list of length topk of tuples having the form (someNode, score). 

If you would like to filter the nodes based on a threshold (ie. nodes similarity >= threshold), you can use the following::

    from neomodel.semantic_filters import VectorFilter
    result = someNode.nodes.filter(
    vector_filter=VectorFilter(
        topk=3, 
        vector_attribute_name="vector", 
        candidate_vector=[0.25, 0.25], 
        threshold=0.85)).all()

Only nodes above threshold = 0.85 will be returned.

The :class:`~neomodel.semantic_filters.VectorFilter` can be used in conjunction with the normal filter types.

.. attention:: 
    If you use VectorFilter in conjunction with normal filter types, only nodes that fit the filters will return thus, you may get less than the topk specified.
    Furthermore, all node filters **should** work with VectorFilter, relationship filters will also work but WILL NOT return the vector similarity score alongside the relationship filter, instead the topk nodes and their appropriate relationships will be returned.

RelationshipProperty
^^^^^^^^^^^^^^^^^^^^
Currently neomodel has not implemented an OGM method for querying vector indexes on relationships.
If this is something that you would like, please submit a GitHub issue with requirements highlighting your usage pattern. 

Alternatively, whilst this has not been implemented yet you can still leverage `db.cypher_query` with the correct syntax to perform your required query. 
