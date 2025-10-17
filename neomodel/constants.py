"""
Constants used in various modules of neomodel.
"""

# Error message constants
RULE_ALREADY_EXISTS = "Neo.ClientError.Schema.EquivalentSchemaRuleAlreadyExists"
INDEX_ALREADY_EXISTS = "Neo.ClientError.Schema.IndexAlreadyExists"
CONSTRAINT_ALREADY_EXISTS = "Neo.ClientError.Schema.ConstraintAlreadyExists"
STREAMING_WARNING = "streaming is not supported by bolt, please remove the kwarg"
NOT_COROUTINE_ERROR = "The decorated function must be a coroutine"

# Access mode constants
ACCESS_MODE_WRITE = "WRITE"
ACCESS_MODE_READ = "READ"

# Database edition constants
ENTERPRISE_EDITION_TAG = "enterprise"

# Neo4j version constants
VERSION_LEGACY_ID = "4"
VERSION_RELATIONSHIP_CONSTRAINTS_SUPPORT = "5.7"
VERSION_PARALLEL_RUNTIME_SUPPORT = "5.13"
VERSION_VECTOR_INDEXES_SUPPORT = "5.15"
VERSION_FULLTEXT_INDEXES_SUPPORT = "5.16"
VERSION_RELATIONSHIP_VECTOR_INDEXES_SUPPORT = "5.18"

# ID method constants
LEGACY_ID_METHOD = "id"
ELEMENT_ID_METHOD = "elementId"

# Cypher query constants
LIST_CONSTRAINTS_COMMAND = "SHOW CONSTRAINTS"
DROP_CONSTRAINT_COMMAND = "DROP CONSTRAINT "
DROP_INDEX_COMMAND = "DROP INDEX "

# Index type constants
LOOKUP_INDEX_TYPE = "LOOKUP"

# Info messages constants
NO_TRANSACTION_IN_PROGRESS = "No transaction in progress"
NO_SESSION_OPEN = "No session open"
UNKNOWN_SERVER_VERSION = """
    Unable to perform this operation because the database server version is not known. 
    This might mean that the database server is offline.
"""
