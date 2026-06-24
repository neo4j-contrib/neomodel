"""
Schema management for the async neomodel module.

``AsyncSchemaManager`` installs and drops indexes and constraints for node and
relationship classes, lists existing schema, and performs admin operations
(clear the database, change a password). It runs Cypher through an
``AsyncQueryRunner`` and reads server version facts from an
``AsyncConnectionManager``.
"""

import sys
from typing import Any, TextIO

from neo4j.exceptions import ClientError

from neomodel.async_.connection import AsyncConnectionManager
from neomodel.async_.query import AsyncQueryRunner
from neomodel.constants import (
    CONSTRAINT_ALREADY_EXISTS,
    DROP_CONSTRAINT_COMMAND,
    DROP_INDEX_COMMAND,
    INDEX_ALREADY_EXISTS,
    LIST_CONSTRAINTS_COMMAND,
    LOOKUP_INDEX_TYPE,
    RULE_ALREADY_EXISTS,
    VERSION_FULLTEXT_INDEXES_SUPPORT,
    VERSION_RELATIONSHIP_CONSTRAINTS_SUPPORT,
    VERSION_RELATIONSHIP_VECTOR_INDEXES_SUPPORT,
    VERSION_VECTOR_INDEXES_SUPPORT,
)
from neomodel.exceptions import FeatureNotSupported
from neomodel.properties import FulltextIndex, Property, VectorIndex
from neomodel.util import escape_cypher_string_literal, escape_identifier


class AsyncSchemaManager:
    """Manages indexes, constraints and schema-related admin operations."""

    def __init__(
        self, connection: AsyncConnectionManager, query_runner: AsyncQueryRunner
    ) -> None:
        self.db: AsyncConnectionManager = connection
        self._query: AsyncQueryRunner = query_runner

    async def list_indexes(self, exclude_token_lookup: bool = False) -> list[dict]:
        """Returns all indexes existing in the database

        Arguments:
            exclude_token_lookup[bool]: Exclude automatically create token lookup indexes

        Returns:
            Sequence[dict]: List of dictionaries, each entry being an index definition
        """
        indexes, meta_indexes = await self._query.cypher_query("SHOW INDEXES")
        indexes_as_dict = [dict(zip(meta_indexes, row)) for row in indexes]

        if exclude_token_lookup:
            indexes_as_dict = [
                obj for obj in indexes_as_dict if obj["type"] != LOOKUP_INDEX_TYPE
            ]

        return indexes_as_dict

    async def list_constraints(self) -> list[dict]:
        """Returns all constraints existing in the database

        Returns:
            Sequence[dict]: List of dictionaries, each entry being a constraint definition
        """
        constraints, meta_constraints = await self._query.cypher_query(
            LIST_CONSTRAINTS_COMMAND
        )
        constraints_as_dict = [dict(zip(meta_constraints, row)) for row in constraints]

        return constraints_as_dict

    async def change_neo4j_password(self, user: str, new_password: str) -> None:
        escaped_user = user.replace("`", "``")
        await self._query.cypher_query(
            f"ALTER USER `{escaped_user}` SET PASSWORD $password",
            {"password": new_password},
        )

    async def clear_neo4j_database(
        self, clear_constraints: bool = False, clear_indexes: bool = False
    ) -> None:
        await self._query.cypher_query(
            """
            MATCH (a)
            CALL { WITH a DETACH DELETE a }
            IN TRANSACTIONS OF 5000 rows
        """
        )
        if clear_constraints:
            await self.drop_constraints()
        if clear_indexes:
            await self.drop_indexes()

    async def drop_constraints(
        self, quiet: bool = True, stdout: TextIO | None = None
    ) -> None:
        """
        Discover and drop all constraints.

        :type: bool
        :return: None
        """
        if not stdout or stdout is None:
            stdout = sys.stdout

        results, meta = await self._query.cypher_query(LIST_CONSTRAINTS_COMMAND)

        results_as_dict = [dict(zip(meta, row)) for row in results]
        for constraint in results_as_dict:
            await self._query.cypher_query(
                DROP_CONSTRAINT_COMMAND + escape_identifier(constraint["name"])
            )
            if not quiet:
                stdout.write(
                    (
                        " - Dropping unique constraint and index"
                        f" on label {constraint['labelsOrTypes'][0]}"
                        f" with property {constraint['properties'][0]}.\n"
                    )
                )
        if not quiet:
            stdout.write("\n")

    async def drop_indexes(
        self, quiet: bool = True, stdout: TextIO | None = None
    ) -> None:
        """
        Discover and drop all indexes, except the automatically created token lookup indexes.

        :type: bool
        :return: None
        """
        if not stdout or stdout is None:
            stdout = sys.stdout

        indexes = await self.list_indexes(exclude_token_lookup=True)
        for index in indexes:
            await self._query.cypher_query(
                DROP_INDEX_COMMAND + escape_identifier(index["name"])
            )
            if not quiet:
                stdout.write(
                    f" - Dropping index on labels {','.join(index['labelsOrTypes'])} with properties {','.join(index['properties'])}.\n"
                )
        if not quiet:
            stdout.write("\n")

    async def remove_all_labels(self, stdout: TextIO | None = None) -> None:
        """
        Calls functions for dropping constraints and indexes.

        :param stdout: output stream
        :return: None
        """

        if not stdout:
            stdout = sys.stdout

        stdout.write("Dropping constraints...\n")
        await self.drop_constraints(quiet=False, stdout=stdout)

        stdout.write("Dropping indexes...\n")
        await self.drop_indexes(quiet=False, stdout=stdout)

    async def install_all_labels(self, stdout: TextIO | None = None) -> None:
        """
        Discover all subclasses of StructuredNode in your application and execute install_labels on each.
        Note: code must be loaded (imported) in order for a class to be discovered.

        :param stdout: output stream
        :return: None
        """

        if not stdout or stdout is None:
            stdout = sys.stdout

        def subsub(cls: Any) -> list:  # recursively return all subclasses
            subclasses = cls.__subclasses__()
            if not subclasses:  # base case: no more subclasses
                return []
            return subclasses + [g for s in cls.__subclasses__() for g in subsub(s)]

        stdout.write("Setting up indexes and constraints...\n\n")

        i = 0
        from neomodel.async_.node import AsyncStructuredNode

        for cls in subsub(AsyncStructuredNode):
            stdout.write(f"Found {cls.__module__}.{cls.__name__}\n")
            await self.install_labels(cls, quiet=False, stdout=stdout)
            i += 1

        if i:
            stdout.write("\n")

        stdout.write(f"Finished {i} classes.\n")

    async def install_labels(
        self, cls: Any, quiet: bool = True, stdout: TextIO | None = None
    ) -> None:
        """
        Setup labels with indexes and constraints for a given class

        :param cls: StructuredNode class
        :type: class
        :param quiet: (default true) enable standard output
        :param stdout: stdout stream
        :type: bool
        :return: None
        """
        _stdout = stdout if stdout else sys.stdout

        if not hasattr(cls, "__label__"):
            if not quiet:
                _stdout.write(
                    f" ! Skipping class {cls.__module__}.{cls.__name__} is abstract\n"
                )
            return

        for name, property in cls.defined_properties(aliases=False, rels=False).items():
            await self._install_node(cls, name, property, quiet, _stdout)

        for _, relationship in cls.defined_properties(
            aliases=False, rels=True, properties=False
        ).items():
            await self._install_relationship(cls, relationship, quiet, _stdout)

    async def _create_node_index(
        self, target_cls: Any, property_name: str, stdout: TextIO, quiet: bool
    ) -> None:
        label = target_cls.__label__
        index_name = f"index_{label}_{property_name}"
        if not quiet:
            stdout.write(
                f" + Creating node index for {property_name} on label {label} for class {target_cls.__module__}.{target_cls.__name__}\n"
            )
        try:
            await self._query.cypher_query(
                f"CREATE INDEX {escape_identifier(index_name)} "
                f"FOR (n:{escape_identifier(label)}) "
                f"ON (n.{escape_identifier(property_name)}); "
            )
        except ClientError as e:
            if e.code in (
                RULE_ALREADY_EXISTS,
                INDEX_ALREADY_EXISTS,
            ):
                stdout.write(f"{str(e)}\n")
            else:
                raise

    async def _create_node_fulltext_index(
        self,
        target_cls: Any,
        property_name: str,
        stdout: TextIO,
        fulltext_index: FulltextIndex,
        quiet: bool,
    ) -> None:
        if await self.db.version_is_higher_than(VERSION_FULLTEXT_INDEXES_SUPPORT):
            label = target_cls.__label__
            index_name = f"fulltext_index_{label}_{property_name}"
            if not quiet:
                stdout.write(
                    f" + Creating fulltext index for {property_name} on label {target_cls.__label__} for class {target_cls.__module__}.{target_cls.__name__}\n"
                )
            query = f"""
                CREATE FULLTEXT INDEX {escape_identifier(index_name)} FOR (n:{escape_identifier(label)}) ON EACH [n.{escape_identifier(property_name)}]
                OPTIONS {{
                    indexConfig: {{
                        `fulltext.analyzer`: '{escape_cypher_string_literal(fulltext_index.analyzer)}',
                        `fulltext.eventually_consistent`: {fulltext_index.eventually_consistent}
                    }}
                }};
            """
            try:
                await self._query.cypher_query(query)
            except ClientError as e:
                if e.code in (
                    RULE_ALREADY_EXISTS,
                    INDEX_ALREADY_EXISTS,
                ):
                    stdout.write(f"{str(e)}\n")
                else:
                    raise
        else:
            raise FeatureNotSupported(
                f"Creation of full-text indexes from neomodel is not supported for Neo4j in version {await self.db.database_version}. Please upgrade to Neo4j 5.16 or higher."
            )

    async def _create_node_vector_index(
        self,
        target_cls: Any,
        property_name: str,
        stdout: TextIO,
        vector_index: VectorIndex,
        quiet: bool,
    ) -> None:
        if await self.db.version_is_higher_than(VERSION_VECTOR_INDEXES_SUPPORT):
            label = target_cls.__label__
            index_name = f"vector_index_{label}_{property_name}"
            if not quiet:
                stdout.write(
                    f" + Creating vector index for {property_name} on label {label} for class {target_cls.__module__}.{target_cls.__name__}\n"
                )
            query = f"""
                CREATE VECTOR INDEX {escape_identifier(index_name)} FOR (n:{escape_identifier(label)}) ON n.{escape_identifier(property_name)}
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {vector_index.dimensions},
                        `vector.similarity_function`: '{escape_cypher_string_literal(vector_index.similarity_function)}'
                    }}
                }};
            """
            try:
                await self._query.cypher_query(query)
            except ClientError as e:
                if e.code in (
                    RULE_ALREADY_EXISTS,
                    INDEX_ALREADY_EXISTS,
                ):
                    stdout.write(f"{str(e)}\n")
                else:
                    raise
        else:
            raise FeatureNotSupported(
                f"Creation of vector indexes from neomodel is not supported for Neo4j in version {await self.db.database_version}. Please upgrade to Neo4j 5.15 or higher."
            )

    async def _create_node_constraint(
        self, target_cls: Any, property_name: str, stdout: TextIO, quiet: bool
    ) -> None:
        label = target_cls.__label__
        constraint_name = f"constraint_unique_{label}_{property_name}"
        if not quiet:
            stdout.write(
                f" + Creating node unique constraint for {property_name} on label {target_cls.__label__} for class {target_cls.__module__}.{target_cls.__name__}\n"
            )
        try:
            await self._query.cypher_query(
                f"""CREATE CONSTRAINT {escape_identifier(constraint_name)}
                            FOR (n:{escape_identifier(label)}) REQUIRE n.{escape_identifier(property_name)} IS UNIQUE"""
            )
        except ClientError as e:
            if e.code in (
                RULE_ALREADY_EXISTS,
                CONSTRAINT_ALREADY_EXISTS,
            ):
                stdout.write(f"{str(e)}\n")
            else:
                raise

    async def _create_relationship_index(
        self,
        relationship_type: str,
        target_cls: Any,
        relationship_cls: Any,
        property_name: str,
        stdout: TextIO,
        quiet: bool,
    ) -> None:
        index_name = f"index_{relationship_type}_{property_name}"
        if not quiet:
            stdout.write(
                f" + Creating relationship index for {property_name} on relationship type {relationship_type} for relationship model {target_cls.__module__}.{relationship_cls.__name__}\n"
            )
        try:
            await self._query.cypher_query(
                f"CREATE INDEX {escape_identifier(index_name)} "
                f"FOR ()-[r:{escape_identifier(relationship_type)}]-() "
                f"ON (r.{escape_identifier(property_name)}); "
            )
        except ClientError as e:
            if e.code in (
                RULE_ALREADY_EXISTS,
                INDEX_ALREADY_EXISTS,
            ):
                stdout.write(f"{str(e)}\n")
            else:
                raise

    async def _create_relationship_fulltext_index(
        self,
        relationship_type: str,
        target_cls: Any,
        relationship_cls: Any,
        property_name: str,
        stdout: TextIO,
        fulltext_index: FulltextIndex,
        quiet: bool,
    ) -> None:
        if await self.db.version_is_higher_than(VERSION_FULLTEXT_INDEXES_SUPPORT):
            index_name = f"fulltext_index_{relationship_type}_{property_name}"
            if not quiet:
                stdout.write(
                    f" + Creating fulltext index for {property_name} on relationship type {relationship_type} for relationship model {target_cls.__module__}.{relationship_cls.__name__}\n"
                )
            query = f"""
                CREATE FULLTEXT INDEX {escape_identifier(index_name)} FOR ()-[r:{escape_identifier(relationship_type)}]-() ON EACH [r.{escape_identifier(property_name)}]
                OPTIONS {{
                    indexConfig: {{
                        `fulltext.analyzer`: '{escape_cypher_string_literal(fulltext_index.analyzer)}',
                        `fulltext.eventually_consistent`: {fulltext_index.eventually_consistent}
                    }}
                }};
            """
            try:
                await self._query.cypher_query(query)
            except ClientError as e:
                if e.code in (
                    RULE_ALREADY_EXISTS,
                    INDEX_ALREADY_EXISTS,
                ):
                    stdout.write(f"{str(e)}\n")
                else:
                    raise
        else:
            raise FeatureNotSupported(
                f"Creation of full-text indexes from neomodel is not supported for Neo4j in version {await self.db.database_version}. Please upgrade to Neo4j 5.16 or higher."
            )

    async def _create_relationship_vector_index(
        self,
        relationship_type: str,
        target_cls: Any,
        relationship_cls: Any,
        property_name: str,
        stdout: TextIO,
        vector_index: VectorIndex,
        quiet: bool,
    ) -> None:
        if await self.db.version_is_higher_than(
            VERSION_RELATIONSHIP_VECTOR_INDEXES_SUPPORT
        ):
            index_name = f"vector_index_{relationship_type}_{property_name}"
            if not quiet:
                stdout.write(
                    f" + Creating vector index for {property_name} on relationship type {relationship_type} for relationship model {target_cls.__module__}.{relationship_cls.__name__}\n"
                )
            query = f"""
                CREATE VECTOR INDEX {escape_identifier(index_name)} FOR ()-[r:{escape_identifier(relationship_type)}]-() ON r.{escape_identifier(property_name)}
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {vector_index.dimensions},
                        `vector.similarity_function`: '{escape_cypher_string_literal(vector_index.similarity_function)}'
                    }}
                }};
            """
            try:
                await self._query.cypher_query(query)
            except ClientError as e:
                if e.code in (
                    RULE_ALREADY_EXISTS,
                    INDEX_ALREADY_EXISTS,
                ):
                    stdout.write(f"{str(e)}\n")
                else:
                    raise
        else:
            raise FeatureNotSupported(
                f"Creation of vector indexes for relationships from neomodel is not supported for Neo4j in version {await self.db.database_version}. Please upgrade to Neo4j 5.18 or higher."
            )

    async def _create_relationship_constraint(
        self,
        relationship_type: str,
        target_cls: Any,
        relationship_cls: Any,
        property_name: str,
        stdout: TextIO,
        quiet: bool,
    ) -> None:
        if await self.db.version_is_higher_than(
            VERSION_RELATIONSHIP_CONSTRAINTS_SUPPORT
        ):
            constraint_name = f"constraint_unique_{relationship_type}_{property_name}"
            if not quiet:
                stdout.write(
                    f" + Creating relationship unique constraint for {property_name} on relationship type {relationship_type} for relationship model {target_cls.__module__}.{relationship_cls.__name__}\n"
                )
            try:
                await self._query.cypher_query(
                    f"""CREATE CONSTRAINT {escape_identifier(constraint_name)}
                                FOR ()-[r:{escape_identifier(relationship_type)}]-() REQUIRE r.{escape_identifier(property_name)} IS UNIQUE"""
                )
            except ClientError as e:
                if e.code in (
                    RULE_ALREADY_EXISTS,
                    CONSTRAINT_ALREADY_EXISTS,
                ):
                    stdout.write(f"{str(e)}\n")
                else:
                    raise
        else:
            raise FeatureNotSupported(
                f"Unique indexes on relationships are not supported in Neo4j version {await self.db.database_version}. Please upgrade to Neo4j 5.7 or higher."
            )

    async def _install_node(
        self, cls: Any, name: str, property: Property, quiet: bool, stdout: TextIO
    ) -> None:
        # Create indexes and constraints for node property
        db_property = property.get_db_property_name(name)
        if property.index:
            await self._create_node_index(
                target_cls=cls, property_name=db_property, stdout=stdout, quiet=quiet
            )
        elif property.unique_index:
            await self._create_node_constraint(
                target_cls=cls, property_name=db_property, stdout=stdout, quiet=quiet
            )

        if property.fulltext_index:
            await self._create_node_fulltext_index(
                target_cls=cls,
                property_name=db_property,
                stdout=stdout,
                fulltext_index=property.fulltext_index,
                quiet=quiet,
            )

        if property.vector_index:
            await self._create_node_vector_index(
                target_cls=cls,
                property_name=db_property,
                stdout=stdout,
                vector_index=property.vector_index,
                quiet=quiet,
            )

    async def _install_relationship(
        self, cls: Any, relationship: Any, quiet: bool, stdout: TextIO
    ) -> None:
        # Create indexes and constraints for relationship property
        relationship_cls = relationship.definition["model"]
        if relationship_cls is not None:
            relationship_type = relationship.definition["relation_type"]
            for prop_name, property in relationship_cls.defined_properties(
                aliases=False, rels=False
            ).items():
                db_property = property.get_db_property_name(prop_name)
                if property.index:
                    await self._create_relationship_index(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        quiet=quiet,
                    )
                elif property.unique_index:
                    await self._create_relationship_constraint(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        quiet=quiet,
                    )

                if property.fulltext_index:
                    await self._create_relationship_fulltext_index(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        fulltext_index=property.fulltext_index,
                        quiet=quiet,
                    )

                if property.vector_index:
                    await self._create_relationship_vector_index(
                        relationship_type=relationship_type,
                        target_cls=cls,
                        relationship_cls=relationship_cls,
                        property_name=db_property,
                        stdout=stdout,
                        vector_index=property.vector_index,
                        quiet=quiet,
                    )
