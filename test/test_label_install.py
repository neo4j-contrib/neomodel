from neomodel import config, StructuredNode, StringProperty
from neomodel.db import client, install_labels, install_all_labels

config.AUTO_INSTALL_LABELS = False


class NoConstraintsSetup(StructuredNode):
    name = StringProperty(unique_index=True)


class AbstractNode(StructuredNode):
    __abstract_node__ = True
    name = StringProperty(unique_index=True)


config.AUTO_INSTALL_LABELS = True


def test_labels_were_not_installed():
    bob = NoConstraintsSetup(name='bob').save()
    bob2 = NoConstraintsSetup(name='bob').save()
    assert bob.id != bob2.id

    for n in NoConstraintsSetup.nodes.all():
        n.delete()


def test_install_all():
    install_labels(AbstractNode)
    # run install all labels
    install_all_labels()
    # remove constraint for above test
    client.cypher_query("DROP CONSTRAINT on (n:NoConstraintsSetup) ASSERT n.name IS UNIQUE")
