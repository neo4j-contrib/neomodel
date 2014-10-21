=======================
Batch creation of nodes
=======================

Atomically create multiple nodes in a single operation, using a single HTTP request::

    people = Person.create(
        {'name': 'Tim', 'age': 83},
        {'name': 'Bob', 'age': 23},
        {'name': 'Jill', 'age': 34},
    )

This is useful for creating large sets of data. It's worth experimenting with the size of batches
to find the optimum performance. A suggestion is to use batch sizes of around 300 to 500 nodes.
