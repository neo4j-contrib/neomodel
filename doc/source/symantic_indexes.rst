.. _Semantic Indexes: 

==================================
Full Text Index 
==================================

From version x.x (version number tbc) neomodel provides a way to interact with neo4j `Full Text indexing <https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/full-text-indexes/>`.


Defining a Full Text Index on a Property
---------------------------------------

Within neomodel, indexing is a decision that is made at class definition time as the index needs to be built. A Full Text index is defined using :class:`~neomodel.properties.FulltextIndex`
To define a property with a full text index we use the following symantics::
    
    StringProperty(fulltext_index=FulltextIndex(analyzer=, eventually_consistent=False)

The index must then be built, this occurs when the function :func:`~neomodel.sync_.core.install_all_labels` or :func:`~neomodel.async_.core.install_all_labels` (depending on whether the nodes you defined as async or sync) is ran.  

The full text index will then have the anme "".

Querying a Full Text Index on a Property
---------------------------------------

This is not currently implemented as a native neomodel query type. If you would like this please submit a github issue highlighting your useage pattern

Alternatively, whilst this has not bbeen implemetned yet you can still leverage `db.cypher_query` with the correct syntax to perform your required query.

==================================
Vector Index 
==================================

From version x.x (version number tbc) neomodel provides a way to interact with neo4j `vector indexing <https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/>`.


Defining a Vector Index on a Property 
--------------------------------------

Within neomodel, indexing is a decision that is made at class definition time as the index needs to be built. A vector index is defined using :class:`~neomodel.properties.VectorIndex`.
To define a property with a vector index we use the following symantics::

    ArrayProperty(base_property=FloatProperty(), vector_index=VectorIndex(dimensions=512, similarity_function="cosine")
    
The index must then be built, this occurs when the function :func:`~neomodel.sync_.core.install_all_labels` or :func:`~neomodel.async_.core.install_all_labels` (depending on whether the nodes you defined as async or sync) is ran.  

The vector indexes will then have the name "vector_index_{node.__label__}_{propertyname_with_vector_index}".

Querying a Vector Index on a Property 
--------------------------------------

Node Property
~~~~~~~~~~
Node properties can be queried using :class:`~neomodel.sync_.vectorfilter.VectorFilter` or 
# Need to document how VectorIndex actually works, send the user to the appropriate neo4j documentation where required. 
# But more importantly the fact that in neomodel they need to specify the vector index on an ARRAYPROPERTY. Furthermore, should make it clear that neomodel creates a new index for each new relation or node that is created with a vector index. There is currently no way to use the same index on two different things. Need to make this clear that this is an implementation issue, not an issue to do with neo4jh thou. 

RelationshipProperty
~~~~~~~~
Currently neomodel has not implemented an OGM method for querying vector indexes on relationships.
If this is something that you like please submit a github issue requirements highlighting your usage pattern. 

Alternatively, whilst this has not been implemented yet you can still leverage `db.cypher_query` with the correct syntax to perform your required query. 

