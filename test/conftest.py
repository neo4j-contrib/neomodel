import os

import pytest

from neomodel.util import version_tag_to_integer

NEO4J_URL = os.environ.get("NEO4J_URL", "bolt://localhost:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "foobarbaz")


def pytest_addoption(parser):
    """
    Adds the command line option --resetdb.

    :param parser: The parser object. Please see <https://docs.pytest.org/en/latest/reference.html#_pytest.hookspec.pytest_addoption>`_
    :type Parser object: For more information please see <https://docs.pytest.org/en/latest/reference.html#_pytest.config.Parser>`_
    """
    parser.addoption(
        "--resetdb",
        action="store_true",
        help="Ensures that the database is clear prior to running tests for neomodel",
        default=False,
    )


@pytest.hookimpl
def pytest_collection_modifyitems(items):
    async_items = []
    sync_items = []
    async_connect_to_aura_items = []
    sync_connect_to_aura_items = []
    root_items = []

    for item in items:
        # Check the directory of the item
        directory = item.fspath.dirname.split("/")[-1]
        if directory == "test_contrib":
            directory = item.fspath.dirname.split("/")[-2]

        if "connect_to_aura" in item.name:
            if directory == "async_":
                async_connect_to_aura_items.append(item)
            elif directory == "sync_":
                sync_connect_to_aura_items.append(item)
        else:
            if directory == "async_":
                async_items.append(item)
            elif directory == "sync_":
                sync_items.append(item)
            else:
                root_items.append(item)

    new_order = (
        async_items
        + async_connect_to_aura_items
        + sync_items
        + root_items
        + sync_connect_to_aura_items
    )
    items[:] = new_order


def check_and_skip_neo4j_least_version(required_least_neo4j_version, message):
    """
    Checks if the NEO4J_VERSION is at least `required_least_neo4j_version` and skips a test if not.

    WARNING: If the NEO4J_VERSION variable is not set, this function returns True, allowing the test to go ahead.

    :param required_least_neo4j_version: The least version to check. This must be the numberic representation of the
    version. That is: '3.4.0' would be passed as 340.
    :type required_least_neo4j_version: int
    :param message: An informative message as to why the calling test had to be skipped.
    :type message: str
    :return: A boolean value of True if the version reported is at least `required_least_neo4j_version`
    """
    if (
        "NEO4J_VERSION" in os.environ
        and version_tag_to_integer(os.environ["NEO4J_VERSION"])
        < required_least_neo4j_version
    ):
        pytest.skip(
            "Neo4j version: {}. {}."
            "Skipping test.".format(os.environ["NEO4J_VERSION"], message)
        )
