# Need to document how VectorIndex actually works, send the user to the appropriate neo4j documentation where required. 
# But more importantly the fact that in neomodel they need to specify the vector index on an ARRAYPROPERTY. Furthermore, should make it clear that neomodel creates a new index for each new relation or node that is created with a vector index. There is currently no way to use the same index on two different things. Need to make this clear that this is an implementation issue, not an issue to do with neo4jh thou. 

# Then need to make it clear how the vectorNode Querying works,
# and metadata filtering. 

# Should make it clear that this operates on a single node type.


# say that VectorRelationship Querying is not yet implemented. 
