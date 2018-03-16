import re
import sys

from neomodel.util import Database


client = Database()


def drop_constraints(quiet=True, stdout=None):
    """
    Discover and drop all constraints.

    :type: bool
    :return: None
    """

    results, meta = client.cypher_query("CALL db.constraints()")
    pattern = re.compile(':(.*) \).*\.(\w*)')
    for constraint in results:
        client.cypher_query('DROP ' + constraint[0])
        match = pattern.search(constraint[0])
        stdout.write(''' - Dropping unique constraint and index on label {} with property {}.\n'''.format(
            match.group(1), match.group(2)))
    stdout.write("\n")


def drop_indexes(quiet=True, stdout=None):
    """
    Discover and drop all indexes.

    :type: bool
    :return: None
    """

    results, meta = client.cypher_query("CALL db.indexes()")
    pattern = re.compile(':(.*)\((.*)\)')
    for index in results:
        client.cypher_query('DROP ' + index[0])
        match = pattern.search(index[0])
        stdout.write(' - Dropping index on label {} with property {}.\n'.format(
            match.group(1), match.group(2)))
    stdout.write("\n")


def remove_all_labels(stdout=None):
    """
    Calls functions for dropping constraints and indexes.

    :param stdout: output stream
    :return: None
    """

    if not stdout:
        stdout = sys.stdout

    stdout.write("Droping constraints...\n")
    drop_constraints(quiet=False, stdout=stdout)

    stdout.write('Droping indexes...\n')
    drop_indexes(quiet=False, stdout=stdout)


def install_labels(cls, quiet=True, stdout=None):
    """
    Setup labels with indexes and constraints for a given class

    :param cls: StructuredNode class
    :type: class
    :param quiet: (default true) enable standard output
    :param stdout: stdout stream
    :type: bool
    :return: None
    """

    if not hasattr(cls, '__label__'):
        if not quiet:
            stdout.write(' ! Skipping class {}.{} is abstract\n'.format(cls.__module__, cls.__name__))
        return

    for name, property in cls.defined_properties(aliases=False, rels=False).items():
        if property.index:
            if not quiet:
                stdout.write(' + Creating index {} on label {} for class {}.{}\n'.format(
                    name, cls.__label__, cls.__module__, cls.__name__))

            client.cypher_query(
                "CREATE INDEX on :{label}({name});"
                .format(label=cls.__label__, name=name)
            )

        elif property.unique_index:
            if not quiet:
                stdout.write(' + Creating unique constraint for {} on label {} for class {}.{}\n'.format(
                    name, cls.__label__, cls.__module__, cls.__name__))

            client.cypher_query(
                "CREATE CONSTRAINT on (n:{label}) ASSERT n.{name} IS UNIQUE;"
                .format(label=cls.__label__, name=name)
            )


def install_all_labels(stdout=None):
    """
    Discover all subclasses of StructuredNode in your application and execute install_labels on each.
    Note: code most be loaded (imported) in order for a class to be discovered.

    :param stdout: output stream
    :return: None
    """
    if 'StructuredNode' not in globals():
        from neomodel.core import StructuredNode
        globals()['StructuredNode'] = StructuredNode

    if not stdout:
        stdout = sys.stdout

    # TODO make that a class method
    def subsub(kls):  # recursively return all subclasses
        return kls.__subclasses__() + [g for s in kls.__subclasses__() for g in subsub(s)]

    stdout.write("Setting up indexes and constraints...\n\n")

    for i, cls in enumerate(subsub(StructuredNode)):
        stdout.write('Found {}.{}\n'.format(cls.__module__, cls.__name__))
        install_labels(cls, quiet=False, stdout=stdout)

    if i:
        stdout.write('\n')

    stdout.write('Finished {} classes.\n'.format(i))
