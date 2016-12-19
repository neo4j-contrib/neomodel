from neomodel import config, StructuredNode, StringProperty, install_all_labels
from neomodel.core import db


config.AUTO_INSTALL_LABELS = False


class NoConstraintsSetup(StructuredNode):
    name = StringProperty(unique_index=True)


config.AUTO_INSTALL_LABELS = True


def test_labels_were_not_installed():
    bob = NoConstraintsSetup(name='bob').save()
    bob2 = NoConstraintsSetup(name='bob').save()
    assert bob.id != bob2.id

    for n in NoConstraintsSetup.nodes.all():
        n.delete()


def test_install_all():
    # run install all labels
    install_all_labels()
    assert True
    # remove constraint for above test
    db.cypher_query("DROP CONSTRAINT on (n:NoConstraintsSetup) ASSERT n.name IS UNIQUE")