"""
Advanced example showing how to use node operations with multiple database instances.

This example demonstrates:
1. Creating a DatabaseContext class to manage database connections
2. Extending node classes to work with specific database instances
3. Performing CRUD operations on different databases
"""

import asyncio
from typing import Any, Generic, Optional, Type, TypeVar

from neomodel.async_.core import AsyncDatabase, AsyncStructuredNode
from neomodel.async_.relationship import AsyncStructuredRel
from neomodel.async_.relationship_manager import AsyncRelationshipTo
from neomodel.properties import IntegerProperty, StringProperty

T = TypeVar("T", bound="MultiDbNode")


class DatabaseContext:
    """
    A context manager for database operations that provides the database instance
    to use for operations.
    """

    _current_db: Optional[AsyncDatabase] = None

    def __init__(self, db: AsyncDatabase):
        self.db = db

    def __enter__(self):
        DatabaseContext._current_db = self.db
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        DatabaseContext._current_db = None

    @classmethod
    def get_current_db(cls) -> AsyncDatabase:
        """Get the current database instance from context"""
        if cls._current_db is None:
            raise RuntimeError(
                "No database context is active. Use 'with DatabaseContext(db):' to set the active database."
            )
        return cls._current_db


class MultiDbNode(AsyncStructuredNode):
    """
    Base class for nodes that can work with multiple database instances.
    This class overrides methods that interact with the database to use
    the database from the current context.
    """

    __abstract_node__ = True

    @classmethod
    async def get_or_create(cls: Type[T], *props, **kwargs) -> list[T]:
        """Override to use the current database context"""
        db = DatabaseContext.get_current_db()

        # Build merge query similar to AsyncStructuredNode.get_or_create
        lazy = kwargs.get("lazy", False)
        relationship = kwargs.get("relationship")

        # Build merge query
        get_or_create_params = [
            {"create": cls.deflate(p, skip_empty=True)} for p in props
        ]

        # Use the build_merge_query method but with our database instance
        query, params = await cls._build_merge_query_with_db(
            db, tuple(get_or_create_params), relationship=relationship, lazy=lazy
        )

        # Execute query with our database
        results = await db.cypher_query(query, params)
        return [cls.inflate(r[0]) for r in results[0]]

    @classmethod
    async def _build_merge_query_with_db(
        cls,
        db: AsyncDatabase,
        merge_params: tuple[dict[str, Any], ...],
        update_existing: bool = False,
        lazy: bool = False,
        relationship: Optional[Any] = None,
    ) -> tuple[str, dict[str, Any]]:
        """Custom version of _build_merge_query that uses the provided database instance"""
        query_params: dict[str, Any] = {"merge_params": merge_params}
        n_merge_labels = ":".join(cls.inherited_labels())
        n_merge_prm = ", ".join(
            (
                f"{getattr(cls, p).get_db_property_name(p)}: params.create.{getattr(cls, p).get_db_property_name(p)}"
                for p in cls.__required_properties__
            )
        )
        n_merge = f"n:{n_merge_labels} {{{n_merge_prm}}}"
        if relationship is None:
            # create "simple" unwind query
            query = f"UNWIND $merge_params as params\n MERGE ({n_merge})\n "
        else:
            # validate relationship
            if not isinstance(relationship.source, AsyncStructuredNode):
                raise ValueError(
                    f"relationship source [{repr(relationship.source)}] is not a StructuredNode"
                )
            relation_type = relationship.definition.get("relation_type")
            if not relation_type:
                raise ValueError(
                    "No relation_type is specified on provided relationship"
                )

            from neomodel.async_.match import _rel_helper

            if relationship.source.element_id is None:
                raise RuntimeError(
                    "Could not identify the relationship source, its element id was None."
                )
            query_params["source_id"] = await db.parse_element_id(
                relationship.source.element_id
            )
            query = f"MATCH (source:{relationship.source.__label__}) WHERE {await db.get_id_method()}(source) = $source_id\n "
            query += "WITH source\n UNWIND $merge_params as params \n "
            query += "MERGE "
            query += _rel_helper(
                lhs="source",
                rhs=n_merge,
                ident=None,
                relation_type=relation_type,
                direction=relationship.definition["direction"],
            )

        query += "ON CREATE SET n = params.create\n "
        # if update_existing, write properties on match as well
        if update_existing is True:
            query += "ON MATCH SET n += params.update\n"

        # close query
        if lazy:
            query += f"RETURN {await db.get_id_method()}(n)"
        else:
            query += "RETURN n"

        return query, query_params


# Define model classes
class User(MultiDbNode):
    """User node class that will be registered with both databases"""

    name = StringProperty(unique_index=True)
    email = StringProperty(index=True)


class Product(MultiDbNode):
    """Product node class that will be registered with both databases"""

    name = StringProperty(index=True)
    price = IntegerProperty()


class Purchase(AsyncStructuredRel):
    """Relationship class for purchases"""

    date = StringProperty()
    quantity = IntegerProperty(default=1)


class Customer(MultiDbNode):
    """Customer node class with relationships"""

    name = StringProperty(unique_index=True)
    purchases = AsyncRelationshipTo(Product, "PURCHASED", model=Purchase)


async def main():
    # Create database instances
    db1 = AsyncDatabase()
    db2 = AsyncDatabase()

    # Set up connections to different databases
    await db1.set_connection(url="bolt://neo4j:password@localhost:7687/db1")
    await db2.set_connection(url="bolt://neo4j:password@localhost:7688/db2")

    # Register node classes with both databases
    User.register_with_database(db1)
    User.register_with_database(db2)
    Product.register_with_database(db1)
    Product.register_with_database(db2)
    Customer.register_with_database(db1)
    Customer.register_with_database(db2)

    # Register relationship class with both databases
    Purchase.register_with_database(db1, "PURCHASED")
    Purchase.register_with_database(db2, "PURCHASED")

    # Example: Create nodes in different databases using the context manager
    with DatabaseContext(db1):
        # Create a user in db1
        alice = (
            await User.get_or_create({"name": "Alice", "email": "alice@example.com"})
        )[0]
        print(f"Created user in db1: {alice.name}")

        # Create a product in db1
        laptop = (await Product.get_or_create({"name": "Laptop", "price": 1000}))[0]
        print(f"Created product in db1: {laptop.name}, ${laptop.price}")

    with DatabaseContext(db2):
        # Create a user in db2
        bob = (await User.get_or_create({"name": "Bob", "email": "bob@example.com"}))[0]
        print(f"Created user in db2: {bob.name}")

        # Create a product in db2
        phone = (await Product.get_or_create({"name": "Phone", "price": 500}))[0]
        print(f"Created product in db2: {phone.name}, ${phone.price}")

    # Verify that the data is in the correct databases
    print("\nVerifying data in db1:")
    results1, _ = await db1.cypher_query("MATCH (n:User) RETURN n.name, n.email")
    print(f"Users in db1: {results1}")

    print("\nVerifying data in db2:")
    results2, _ = await db2.cypher_query("MATCH (n:User) RETURN n.name, n.email")
    print(f"Users in db2: {results2}")

    # Clean up
    await db1.close_connection()
    await db2.close_connection()


if __name__ == "__main__":
    asyncio.run(main())
