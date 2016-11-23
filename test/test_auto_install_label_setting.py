from neomodel import config, StructuredNode, StringProperty


config.AUTO_INSTALL_LABELS = False


class NoConstraintsSetup(StructuredNode):
    name = StringProperty(unique_index=True)


config.AUTO_INSTALL_LABELS = True


def test_labels_were_not_installed():
    bob = NoConstraintsSetup(name='bob').save()
    bob2 = NoConstraintsSetup(name='bob').save()
    assert bob.id != bob2.id