from neomodel import (
    ArrayProperty,
    AsyncRelationshipTo,
    AsyncStructuredNode,
    BooleanProperty,
    DateProperty,
    DateTimeFormatProperty,
    DateTimeProperty,
    FloatProperty,
    IntegerProperty,
    RelationshipFrom,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    UniqueIdProperty,
)
from neomodel.contrib.spatial_properties import PointProperty


class Document(StructuredNode):
    uid = UniqueIdProperty()
    unique_prop = StringProperty(unique_index=True)
    title = StringProperty(required=True, indexed=True)
    publication_date = DateProperty()
    number_of_words = IntegerProperty()
    embedding = ArrayProperty(FloatProperty())

    # Outgoing rels
    has_author = RelationshipTo("Author", "HAS_AUTHOR")
    has_description = RelationshipTo("Description", "HAS_DESCRIPTION")
    has_abstract = RelationshipTo("Abstract", "HAS_ABSTRACT")

    # Incoming rel
    approved_by = RelationshipFrom("Approval", "APPROVED")

    # Same-label rel
    cites = RelationshipTo("Document", "CITES")


class Author(StructuredNode):
    name = StringProperty(index=True)

    in_office = RelationshipTo("Office", "IN_OFFICE")


class Office(StructuredNode):
    location = PointProperty(unique_index=True, crs="cartesian")


class Approval(StructuredNode):
    approval_datetime = DateTimeProperty()
    approval_local_datetime = DateTimeFormatProperty()
    approved = BooleanProperty(default=False)

    approved_by = RelationshipTo("Author", "APPROVED_BY")


class Description(StructuredNode):
    uid = UniqueIdProperty()
    content = StringProperty()


class Abstract(StructuredNode):
    uid = UniqueIdProperty()
    content = StringProperty()


class AsyncNeighbour(AsyncStructuredNode):
    uid = UniqueIdProperty()
    name = StringProperty()

    has_async_neighbour = AsyncRelationshipTo("AsyncNeighbour", "HAS_ASYNC_NEIGHBOUR")
    has_other_async_neighbour = AsyncRelationshipTo(
        "OtherAsyncNeighbour", "HAS_OTHER_ASYNC_NEIGHBOUR"
    )


class OtherAsyncNeighbour(AsyncStructuredNode):
    uid = UniqueIdProperty()
    unique_prop = StringProperty(unique_index=True)
    order = IntegerProperty(required=True, indexed=True)
