"""
Example showing how to use multiple database instances with neomodel.

This example demonstrates:
1. Creating multiple database instances
2. Registering node and relationship classes with different database instances
3. Performing operations on different databases
"""

import asyncio

from neomodel.async_.core import AsyncDatabase, AsyncStructuredNode
from neomodel.async_.relationship import AsyncStructuredRel
from neomodel.async_.relationship_manager import AsyncRelationshipTo
from neomodel.properties import IntegerProperty, StringProperty

# Create database instances
db1 = AsyncDatabase()  # First database instance
db2 = AsyncDatabase()  # Second database instance


# Define node classes
class User(AsyncStructuredNode):
    """User node class that will be registered with both databases"""

    name = StringProperty(unique_index=True)
    email = StringProperty(index=True)


class Product(AsyncStructuredNode):
    """Product node class that will be registered with both databases"""

    name = StringProperty(index=True)
    price = IntegerProperty()


# Define relationship class
class Purchased(AsyncStructuredRel):
    """Relationship class for purchases"""

    date = StringProperty()
    quantity = IntegerProperty(default=1)


# Define a node class with relationships
class Customer(AsyncStructuredNode):
    """Customer node class with relationships"""

    name = StringProperty(unique_index=True)
    purchases = AsyncRelationshipTo(Product, "PURCHASED", model=Purchased)


async def main():
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
    Purchased.register_with_database(db1, "PURCHASED")
    Purchased.register_with_database(db2, "PURCHASED")

    # Example: Execute raw Cypher queries on different databases
    print("Running queries on db1:")
    results1, _ = await db1.cypher_query("CREATE (n:User {name: 'Alice'}) RETURN n")
    results1, _ = await db1.cypher_query("MATCH (n:User) RETURN n.name")
    print(f"Users in db1: {[row[0] for row in results1]}")

    print("\nRunning queries on db2:")
    results2, _ = await db2.cypher_query("CREATE (n:User {name: 'Bob'}) RETURN n")
    results2, _ = await db2.cypher_query("MATCH (n:User) RETURN n.name")
    print(f"Users in db2: {[row[0] for row in results2]}")

    # Example: Using object resolution with different databases
    print("\nUsing object resolution:")
    results1, _ = await db1.cypher_query(
        "MATCH (n:User) RETURN n", resolve_objects=True
    )
    print(f"User from db1: {results1[0][0].name}")

    results2, _ = await db2.cypher_query(
        "MATCH (n:User) RETURN n", resolve_objects=True
    )
    print(f"User from db2: {results2[0][0].name}")

    # Clean up
    await db1.close_connection()
    await db2.close_connection()


if __name__ == "__main__":
    asyncio.run(main())
