from neo4j.graph import Relationship as Relationship
from neomodel.hooks import hooks as hooks
from neomodel.properties import Property as Property
from neomodel.sync_.database import db as db
from neomodel.sync_.property_manager import PropertyManager as PropertyManager
from typing import Any

ELEMENT_ID_MIGRATION_NOTICE: str

class RelationshipMeta(type):
    def __new__(mcs: type, name: str, bases: tuple[type, ...], dct: dict[str, Any]) -> Any: ...

class StructuredRelBase(PropertyManager, metaclass=RelationshipMeta): ...

class StructuredRel(StructuredRelBase):
    element_id_property: str
    @property
    def element_id(self) -> str | None: ...
    @property
    def id(self) -> int: ...
    @hooks
    def save(self) -> StructuredRel: ...
    def start_node(self) -> Any: ...
    def end_node(self) -> Any: ...
    @classmethod
    def inflate(cls, graph_entity: Relationship) -> StructuredRel: ...  # type: ignore[override]
