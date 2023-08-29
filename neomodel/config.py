import neo4j

from ._version import __version__

AUTO_INSTALL_LABELS = False
DATABASE_URL = "bolt://neo4j:foobarbaz@localhost:7687"
FORCE_TIMEZONE = False

CONNECTION_ACQUISITION_TIMEOUT = 60.0
CONNECTION_TIMEOUT = 30.0
ENCRYPTED = False
KEEP_ALIVE = True
MAX_CONNECTION_LIFETIME = 3600
MAX_CONNECTION_POOL_SIZE = 100
MAX_TRANSACTION_RETRY_TIME = 30.0
RESOLVER = None
TRUSTED_CERTIFICATES = neo4j.TrustSystemCAs()
USER_AGENT = f"neomodel/v{__version__}"

DRIVER = neo4j.GraphDatabase().driver(
    "bolt://localhost:7687", auth=("neo4j", "foobarbaz")
)
# TODO : Try passing a different database name
# DATABASE_NAME = "testdatabase"
