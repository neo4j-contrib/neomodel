from .properties import Property, PropertyManager


class RelationshipMeta(type):
    def __new__(mcs, name, bases, dct):
        inst = super(RelationshipMeta, mcs).__new__(mcs, name, bases, dct)
        for key, value in dct.items():
            if issubclass(value.__class__, Property):
                value.name = key
                value.owner = inst
                if value.is_indexed:
                    raise NotImplemented("Indexed relationship properties not supported yet")

                # support for 'magic' properties
                if hasattr(value, 'setup') and hasattr(value.setup, '__call__'):
                    value.setup()
        return inst


RelationshipBase = RelationshipMeta('RelationshipBase', (PropertyManager,), {})


class Relationship(RelationshipBase):
    def __init__(self, *args, **kwargs):
        super(Relationship, self).__init__(*args, **kwargs)
