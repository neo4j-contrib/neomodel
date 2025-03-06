import inspect
import re
import string
from dataclasses import dataclass
from typing import Any, Iterator
from typing import Optional as TOptional
from typing import Tuple, Union

from neomodel.exceptions import MultipleNodesReturned
from neomodel.match_q import Q, QBase
from neomodel.properties import AliasProperty, ArrayProperty, Property
from neomodel.sync_ import relationship_manager
from neomodel.sync_.core import StructuredNode, db
from neomodel.sync_.relationship import StructuredRel
from neomodel.typing import Subquery, Transformation
from neomodel.util import INCOMING, OUTGOING

CYPHER_ACTIONS_WITH_SIDE_EFFECT_EXPR = re.compile(r"(?i:MERGE|CREATE|DELETE|DETACH)")


def _rel_helper(
    lhs: str,
    rhs: str,
    ident: TOptional[str] = None,
    relation_type: TOptional[str] = None,
    direction: TOptional[int] = None,
    relation_properties: TOptional[dict] = None,
    **kwargs: dict[str, Any],  # NOSONAR
) -> str:
    """
    Generate a relationship matching string, with specified parameters.
    Examples:
    relation_direction = OUTGOING: (lhs)-[relation_ident:relation_type]->(rhs)
    relation_direction = INCOMING: (lhs)<-[relation_ident:relation_type]-(rhs)
    relation_direction = EITHER: (lhs)-[relation_ident:relation_type]-(rhs)

    :param lhs: The left hand statement.
    :type lhs: str
    :param rhs: The right hand statement.
    :type rhs: str
    :param ident: A specific identity to name the relationship, or None.
    :type ident: str
    :param relation_type: None for all direct rels, * for all of any length, or a name of an explicit rel.
    :type relation_type: str
    :param direction: None or EITHER for all OUTGOING,INCOMING,EITHER. Otherwise OUTGOING or INCOMING.
    :param relation_properties: dictionary of relationship properties to match
    :returns: string
    """
    rel_props = ""

    if relation_properties:
        rel_props_str = ", ".join(
            (f"{key}: {value}" for key, value in relation_properties.items())
        )
        rel_props = f" {{{rel_props_str}}}"

    rel_def = ""
    # relation_type is unspecified
    if relation_type is None:
        rel_def = ""
    # all("*" wildcard) relation_type
    elif relation_type == "*":
        rel_def = "[*]"
    else:
        # explicit relation_type
        rel_def = f"[{ident if ident else ''}:`{relation_type}`{rel_props}]"

    stmt = ""
    if direction == OUTGOING:
        stmt = f"-{rel_def}->"
    elif direction == INCOMING:
        stmt = f"<-{rel_def}-"
    else:
        stmt = f"-{rel_def}-"

    # Make sure not to add parenthesis when they are already present
    if lhs[-1] != ")":
        lhs = f"({lhs})"
    if rhs[-1] != ")":
        rhs = f"({rhs})"

    return f"{lhs}{stmt}{rhs}"


def _rel_merge_helper(
    lhs: str,
    rhs: str,
    ident: str = "neomodelident",
    relation_type: TOptional[str] = None,
    direction: TOptional[int] = None,
    relation_properties: TOptional[dict] = None,
    **kwargs: dict[str, Any],  # NOSONAR
) -> str:
    """
    Generate a relationship merging string, with specified parameters.
    Examples:
    relation_direction = OUTGOING: (lhs)-[relation_ident:relation_type]->(rhs)
    relation_direction = INCOMING: (lhs)<-[relation_ident:relation_type]-(rhs)
    relation_direction = EITHER: (lhs)-[relation_ident:relation_type]-(rhs)

    :param lhs: The left hand statement.
    :type lhs: str
    :param rhs: The right hand statement.
    :type rhs: str
    :param ident: A specific identity to name the relationship, or None.
    :type ident: str
    :param relation_type: None for all direct rels, * for all of any length, or a name of an explicit rel.
    :type relation_type: str
    :param direction: None or EITHER for all OUTGOING,INCOMING,EITHER. Otherwise OUTGOING or INCOMING.
    :param relation_properties: dictionary of relationship properties to merge
    :returns: string
    """

    if direction == OUTGOING:
        stmt = "-{0}->"
    elif direction == INCOMING:
        stmt = "<-{0}-"
    else:
        stmt = "-{0}-"

    rel_props = ""
    rel_none_props = ""

    if relation_properties:
        rel_props_str = ", ".join(
            (
                f"{key}: {value}"
                for key, value in relation_properties.items()
                if value is not None
            )
        )
        rel_props = f" {{{rel_props_str}}}"
        if None in relation_properties.values():
            rel_prop_val_str = ", ".join(
                (
                    f"{ident}.{key}=${key!s}"
                    for key, value in relation_properties.items()
                    if value is None
                )
            )
            rel_none_props = (
                f" ON CREATE SET {rel_prop_val_str} ON MATCH SET {rel_prop_val_str}"
            )
    # relation_type is unspecified
    if relation_type is None:
        stmt = stmt.format("")
    # all("*" wildcard) relation_type
    elif relation_type == "*":
        stmt = stmt.format("[*]")
    else:
        # explicit relation_type
        stmt = stmt.format(f"[{ident}:`{relation_type}`{rel_props}]")

    return f"({lhs}){stmt}({rhs}){rel_none_props}"


# special operators
_SPECIAL_OPERATOR_IN = "IN"
_SPECIAL_OPERATOR_ARRAY_IN = "any(x IN {ident}.{prop} WHERE x IN {val})"
_SPECIAL_OPERATOR_INSENSITIVE = "(?i)"
_SPECIAL_OPERATOR_ISNULL = "IS NULL"
_SPECIAL_OPERATOR_ISNOTNULL = "IS NOT NULL"
_SPECIAL_OPERATOR_REGEX = "=~"

_UNARY_OPERATORS = (_SPECIAL_OPERATOR_ISNULL, _SPECIAL_OPERATOR_ISNOTNULL)

_REGEX_INSENSITIVE = _SPECIAL_OPERATOR_INSENSITIVE + "{}"
_REGEX_CONTAINS = ".*{}.*"
_REGEX_STARTSWITH = "{}.*"
_REGEX_ENDSWITH = ".*{}"

# regex operations that require escaping
_STRING_REGEX_OPERATOR_TABLE = {
    "iexact": _REGEX_INSENSITIVE,
    "contains": _REGEX_CONTAINS,
    "icontains": _SPECIAL_OPERATOR_INSENSITIVE + _REGEX_CONTAINS,
    "startswith": _REGEX_STARTSWITH,
    "istartswith": _SPECIAL_OPERATOR_INSENSITIVE + _REGEX_STARTSWITH,
    "endswith": _REGEX_ENDSWITH,
    "iendswith": _SPECIAL_OPERATOR_INSENSITIVE + _REGEX_ENDSWITH,
}
# regex operations that do not require escaping
_REGEX_OPERATOR_TABLE = {
    "iregex": _REGEX_INSENSITIVE,
}
# list all regex operations, these will require formatting of the value
_REGEX_OPERATOR_TABLE.update(_STRING_REGEX_OPERATOR_TABLE)

# list all supported operators
OPERATOR_TABLE = {
    "lt": "<",
    "gt": ">",
    "lte": "<=",
    "gte": ">=",
    "ne": "<>",
    "in": _SPECIAL_OPERATOR_IN,
    "isnull": _SPECIAL_OPERATOR_ISNULL,
    "regex": _SPECIAL_OPERATOR_REGEX,
    "exact": "=",
}
# add all regex operators
OPERATOR_TABLE.update(_REGEX_OPERATOR_TABLE)

path_split_regex = re.compile(r"__(?!_)|\|")


def install_traversals(cls: type[StructuredNode], node_set: "NodeSet") -> None:
    """
    For a StructuredNode class install Traversal objects for each
    relationship definition on a NodeSet instance
    """
    rels = cls.defined_properties(rels=True, aliases=False, properties=False)

    for key in rels.keys():
        if hasattr(node_set, key):
            raise ValueError(f"Cannot install traversal '{key}' exists on NodeSet")

        rel = getattr(cls, key)
        rel.lookup_node_class()

        traversal = Traversal(source=node_set, name=key, definition=rel.definition)
        setattr(node_set, key, traversal)


def _handle_special_operators(
    property_obj: Property, key: str, value: str, operator: str, prop: str
) -> Tuple[str, str, str]:
    if operator == _SPECIAL_OPERATOR_IN:
        if not isinstance(value, (list, tuple)):
            raise ValueError(
                f"Value must be a tuple or list for IN operation {key}={value}"
            )
        if isinstance(property_obj, ArrayProperty):
            deflated_value = property_obj.deflate(value)
            operator = _SPECIAL_OPERATOR_ARRAY_IN
        else:
            deflated_value = [property_obj.deflate(v) for v in value]
    elif operator == _SPECIAL_OPERATOR_ISNULL:
        if not isinstance(value, bool):
            raise ValueError(f"Value must be a bool for isnull operation on {key}")
        operator = "IS NULL" if value else "IS NOT NULL"
        deflated_value = None
    elif operator in _REGEX_OPERATOR_TABLE.values():
        deflated_value = property_obj.deflate(value)
        if not isinstance(deflated_value, str):
            raise ValueError(f"Must be a string value for {key}")
        if operator in _STRING_REGEX_OPERATOR_TABLE.values():
            deflated_value = re.escape(deflated_value)
        deflated_value = operator.format(deflated_value)
        operator = _SPECIAL_OPERATOR_REGEX
    else:
        deflated_value = property_obj.deflate(value)

    return deflated_value, operator, prop


def _deflate_value(
    cls: type[StructuredNode],
    property_obj: Property,
    key: str,
    value: str,
    operator: str,
    prop: str,
) -> Tuple[str, str, str]:
    if isinstance(property_obj, AliasProperty):
        prop = property_obj.aliased_to()
        deflated_value = getattr(cls, prop).deflate(value)
    else:
        # handle special operators
        deflated_value, operator, prop = _handle_special_operators(
            property_obj, key, value, operator, prop
        )

    return deflated_value, operator, prop


def _initialize_filter_args_variables(
    cls: type[StructuredNode], key: str
) -> Tuple[type[StructuredNode], None, None, str, bool, str]:
    current_class = cls
    current_rel_model = None
    leaf_prop = None
    operator = "="
    is_rel_property = "|" in key
    prop = key

    return (
        current_class,
        current_rel_model,
        leaf_prop,
        operator,
        is_rel_property,
        prop,
    )


def _process_filter_key(
    cls: type[StructuredNode], key: str
) -> Tuple[Property, str, str]:
    (
        current_class,
        current_rel_model,
        leaf_prop,
        operator,
        is_rel_property,
        prop,
    ) = _initialize_filter_args_variables(cls, key)

    for part in re.split(path_split_regex, key):
        defined_props = current_class.defined_properties(rels=True)
        # update defined props dictionary with relationship properties if
        # we are filtering by property
        if is_rel_property and current_rel_model:
            defined_props.update(current_rel_model.defined_properties(rels=True))
        if part in defined_props:
            if isinstance(
                defined_props[part], relationship_manager.RelationshipDefinition
            ):
                defined_props[part].lookup_node_class()
                current_class = defined_props[part].definition["node_class"]
                current_rel_model = defined_props[part].definition["model"]
        elif part in OPERATOR_TABLE:
            operator = OPERATOR_TABLE[part]
            prop, _ = prop.rsplit("__", 1)
            continue
        else:
            raise ValueError(
                f"No such property {part} on {cls.__name__}. Note that Neo4j internals like id or element_id are not allowed for use in this operation."
            )
        leaf_prop = part

    if leaf_prop is None:
        raise ValueError(f"Badly formed filter, no property found in {key}")
    if is_rel_property and current_rel_model:
        property_obj = getattr(current_rel_model, leaf_prop)
    else:
        property_obj = getattr(current_class, leaf_prop)

    return property_obj, operator, prop


def process_filter_args(cls: type[StructuredNode], kwargs: dict[str, Any]) -> dict:
    """
    loop through properties in filter parameters check they match class definition
    deflate them and convert into something easy to generate cypher from
    """
    output = {}

    for key, value in kwargs.items():
        property_obj, operator, prop = _process_filter_key(cls, key)
        deflated_value, operator, prop = _deflate_value(
            cls, property_obj, key, value, operator, prop
        )
        # map property to correct property name in the database
        db_property = prop

        output[db_property] = (operator, deflated_value)
    return output


def process_has_args(
    cls: type[StructuredNode], kwargs: dict[str, Any]
) -> tuple[dict, dict]:
    """
    loop through has parameters check they correspond to class rels defined
    """
    rel_definitions = cls.defined_properties(properties=False, rels=True, aliases=False)

    match, dont_match = {}, {}

    for key, value in kwargs.items():
        if key not in rel_definitions:
            raise ValueError(f"No such relation {key} defined on a {cls.__name__}")

        rhs_ident = key

        rel_definitions[key].lookup_node_class()

        if value is True:
            match[rhs_ident] = rel_definitions[key].definition
        elif value is False:
            dont_match[rhs_ident] = rel_definitions[key].definition
        elif isinstance(value, NodeSet):
            raise NotImplementedError("Not implemented yet")
        else:
            raise ValueError("Expecting True / False / NodeSet got: " + repr(value))

    return match, dont_match


class QueryAST:
    match: list[str]
    optional_match: list[str]
    where: list[str]
    with_clause: TOptional[str]
    return_clause: TOptional[str]
    order_by: TOptional[list[str]]
    skip: TOptional[int]
    limit: TOptional[int]
    result_class: TOptional[type]
    lookup: TOptional[str]
    additional_return: TOptional[list[str]]
    is_count: TOptional[bool]

    def __init__(
        self,
        match: TOptional[list[str]] = None,
        optional_match: TOptional[list[str]] = None,
        where: TOptional[list[str]] = None,
        optional_where: TOptional[list[str]] = None,
        with_clause: TOptional[str] = None,
        return_clause: TOptional[str] = None,
        order_by: TOptional[list[str]] = None,
        skip: TOptional[int] = None,
        limit: TOptional[int] = None,
        result_class: TOptional[type] = None,
        lookup: TOptional[str] = None,
        additional_return: TOptional[list[str]] = None,
        is_count: TOptional[bool] = False,
    ) -> None:
        self.match = match if match else []
        self.optional_match = optional_match if optional_match else []
        self.where = where if where else []
        self.optional_where = optional_where if optional_where else []
        self.with_clause = with_clause
        self.return_clause = return_clause
        self.order_by = order_by
        self.skip = skip
        self.limit = limit
        self.result_class = result_class
        self.lookup = lookup
        self.additional_return: list[str] = (
            additional_return if additional_return else []
        )
        self.is_count = is_count
        self.subgraph: dict = {}


class QueryBuilder:
    def __init__(
        self, node_set: "BaseSet", subquery_namespace: TOptional[str] = None
    ) -> None:
        self.node_set = node_set
        self._ast = QueryAST()
        self._query_params: dict = {}
        self._place_holder_registry: dict = {}
        self._relation_identifier_count: int = 0
        self._node_identifier_count: int = 0
        self._subquery_namespace: TOptional[str] = subquery_namespace

    def build_ast(self) -> "QueryBuilder":
        if isinstance(self.node_set, NodeSet) and hasattr(
            self.node_set, "relations_to_fetch"
        ):
            for relation in self.node_set.relations_to_fetch:
                self.build_traversal_from_path(relation, self.node_set.source)

        self.build_source(self.node_set)

        if hasattr(self.node_set, "skip"):
            self._ast.skip = self.node_set.skip
        if hasattr(self.node_set, "limit"):
            self._ast.limit = self.node_set.limit

        return self

    def build_source(
        self, source: Union["Traversal", "NodeSet", StructuredNode, Any]
    ) -> str:
        if isinstance(source, Traversal):
            return self.build_traversal(source)
        if isinstance(source, NodeSet):
            if inspect.isclass(source.source) and issubclass(
                source.source, StructuredNode
            ):
                ident = self.build_label(source.source.__label__.lower(), source.source)
            else:
                ident = self.build_source(source.source)

            self.build_additional_match(ident, source)

            if hasattr(source, "order_by_elements"):
                self.build_order_by(ident, source)

            # source.filters seems to be used only by Traversal objects
            # source.q_filters is used by NodeSet objects
            if source.filters or source.q_filters:
                self.build_where_stmt(
                    ident=ident,
                    filters=source.filters,
                    source_class=source.source_class,
                    q_filters=source.q_filters,
                )

            return ident
        if isinstance(source, StructuredNode):
            return self.build_node(source)
        raise ValueError("Unknown source type " + repr(source))

    def create_relation_identifier(self) -> str:
        self._relation_identifier_count += 1
        return f"r{self._relation_identifier_count}"

    def create_node_identifier(self, prefix: str) -> str:
        self._node_identifier_count += 1
        return f"{prefix}{self._node_identifier_count}"

    def build_order_by(self, ident: str, source: "NodeSet") -> None:
        if "?" in source.order_by_elements:
            self._ast.with_clause = f"{ident}, rand() as r"
            self._ast.order_by = ["r"]
        else:
            order_by = []
            for elm in source.order_by_elements:
                if isinstance(elm, RawCypher):
                    order_by.append(elm.render({"n": ident}))
                    continue
                is_rel_property = "|" in elm
                if "__" not in elm and not is_rel_property:
                    prop = elm.split(" ")[0] if " " in elm else elm
                    if prop not in source.source_class.defined_properties(rels=False):
                        raise ValueError(
                            f"No such property {prop} on {source.source_class.__name__}. "
                            f"Note that Neo4j internals like id or element_id are not allowed "
                            f"for use in this operation."
                        )
                    order_by.append(f"{ident}.{elm}")
                else:
                    path, prop = elm.rsplit("__" if not is_rel_property else "|", 1)
                    result = self.lookup_query_variable(
                        path, return_relation=is_rel_property
                    )
                    if result:
                        order_by.append(f"{result[0]}.{prop}")
            self._ast.order_by = order_by

    def build_traversal(self, traversal: "Traversal") -> str:
        """
        traverse a relationship from a node to a set of nodes
        """
        # build source
        rhs_label = ":" + traversal.target_class.__label__

        # build source
        rel_ident = self.create_relation_identifier()
        lhs_ident = self.build_source(traversal.source)
        traversal_ident = f"{traversal.name}_{rel_ident}"
        rhs_ident = traversal_ident + rhs_label
        self._ast.return_clause = traversal_ident
        self._ast.result_class = traversal.target_class

        stmt = _rel_helper(
            lhs=lhs_ident,
            rhs=rhs_ident,
            ident=rel_ident,
            **traversal.definition,
        )
        self._ast.match.append(stmt)

        if traversal.filters:
            self.build_where_stmt(rel_ident, traversal.filters, traversal.source_class)

        return traversal_ident

    def _additional_return(self, name: str) -> None:
        if (
            not self._ast.additional_return or name not in self._ast.additional_return
        ) and name != self._ast.return_clause:
            if not self._ast.additional_return:
                self._ast.additional_return = []
            self._ast.additional_return.append(name)

    def build_traversal_from_path(
        self, relation: dict, source_class: Any
    ) -> Tuple[str, Any]:
        path: str = relation["path"]
        stmt: str = ""
        source_class_iterator = source_class
        parts = re.split(path_split_regex, path)
        subgraph = self._ast.subgraph
        rel_iterator: str = ""
        already_present = False
        existing_rhs_name = ""
        for index, part in enumerate(parts):
            relationship = getattr(source_class_iterator, part)
            if rel_iterator:
                rel_iterator += "__"
            rel_iterator += part
            # build source
            if "node_class" not in relationship.definition:
                relationship.lookup_node_class()
            if not stmt:
                lhs_label = source_class_iterator.__label__
                lhs_name = lhs_label.lower()
                lhs_ident = f"{lhs_name}:{lhs_label}"
                if not index:
                    # This is the first one, we make sure that 'return'
                    # contains the primary node so _contains() works
                    # as usual
                    self._ast.return_clause = lhs_name
                    if self._subquery_namespace:
                        # Don't include label in identifier if we are in a subquery
                        lhs_ident = lhs_name
                elif relation["include_in_return"]:
                    self._additional_return(lhs_name)
            else:
                lhs_ident = stmt

            already_present = part in subgraph
            rel_ident = self.create_relation_identifier()
            rhs_label = relationship.definition["node_class"].__label__
            if relation.get("relation_filtering"):
                rhs_name = rel_ident
            else:
                if index + 1 == len(parts) and "alias" in relation:
                    # If an alias is defined, use it to store the last hop in the path
                    rhs_name = relation["alias"]
                else:
                    rhs_name = f"{rhs_label.lower()}_{rel_iterator}"
                    rhs_name = self.create_node_identifier(rhs_name)
            rhs_ident = f"{rhs_name}:{rhs_label}"
            if relation["include_in_return"] and not already_present:
                self._additional_return(rhs_name)

            if not already_present:
                subgraph[part] = {
                    "target": relationship.definition["node_class"],
                    "children": {},
                    "variable_name": rhs_name,
                    "rel_variable_name": rel_ident,
                }
            else:
                existing_rhs_name = subgraph[part][
                    (
                        "rel_variable_name"
                        if relation.get("relation_filtering")
                        else "variable_name"
                    )
                ]
            if relation["include_in_return"] and not already_present:
                self._additional_return(rel_ident)
            stmt = _rel_helper(
                lhs=lhs_ident,
                rhs=rhs_ident,
                ident=rel_ident,
                direction=relationship.definition["direction"],
                relation_type=relationship.definition["relation_type"],
            )
            source_class_iterator = relationship.definition["node_class"]
            subgraph = subgraph[part]["children"]

        if not already_present:
            if relation.get("optional"):
                self._ast.optional_match.append(stmt)
            else:
                self._ast.match.append(stmt)
            return rhs_name, relationship.definition["node_class"]

        return existing_rhs_name, relationship.definition["node_class"]

    def build_node(self, node: StructuredNode) -> str:
        ident = node.__class__.__name__.lower()
        place_holder = self._register_place_holder(ident)

        # Hack to emulate START to lookup a node by id
        _node_lookup = f"MATCH ({ident}) WHERE {db.get_id_method()}({ident})=${place_holder} WITH {ident}"
        self._ast.lookup = _node_lookup

        self._query_params[place_holder] = db.parse_element_id(node.element_id)

        self._ast.return_clause = ident
        self._ast.result_class = node.__class__
        return ident

    def build_label(self, ident: str, cls: type[StructuredNode]) -> str:
        """
        match nodes by a label
        """
        ident_w_label = ident + ":" + cls.__label__

        if not self._ast.return_clause:
            if (
                not self._ast.additional_return
                or ident not in self._ast.additional_return
            ):
                self._ast.match.append(f"({ident_w_label})")
                self._ast.return_clause = ident
                self._ast.result_class = cls
        elif not self._ast.match:
            # If we get here, it means return_clause was filled because of an
            # optional match, so we add a regular match for root node.
            # Not very elegant, this part would deserve a refactoring...
            self._ast.match.append(f"({ident_w_label})")
            self._ast.result_class = cls
        return ident

    def build_additional_match(self, ident: str, node_set: "NodeSet") -> None:
        """
        handle additional matches supplied by 'has()' calls
        """
        source_ident = ident

        for _, value in node_set.must_match.items():
            if isinstance(value, dict):
                label = ":" + value["node_class"].__label__
                stmt = f"EXISTS ({_rel_helper(lhs=source_ident, rhs=label, ident='', **value)})"
                self._ast.where.append(stmt)
            else:
                raise ValueError("Expecting dict got: " + repr(value))

        for _, val in node_set.dont_match.items():
            if isinstance(val, dict):
                label = ":" + val["node_class"].__label__
                stmt = f"NOT EXISTS ({_rel_helper(lhs=source_ident, rhs=label, ident='', **val)})"
                self._ast.where.append(stmt)
            else:
                raise ValueError("Expecting dict got: " + repr(val))

    def _register_place_holder(self, key: str) -> str:
        if key in self._place_holder_registry:
            self._place_holder_registry[key] += 1
        else:
            self._place_holder_registry[key] = 1
        place_holder = f"{key}_{self._place_holder_registry[key]}"
        if self._subquery_namespace:
            place_holder = f"{self._subquery_namespace}_{place_holder}"
        return place_holder

    def _parse_path(
        self, source_class: type[StructuredNode], prop: str
    ) -> Tuple[str, str, str, Any, bool]:
        is_rel_filter = "|" in prop
        if is_rel_filter:
            path, prop = prop.rsplit("|", 1)
        else:
            path, prop = prop.rsplit("__", 1)
        result = self.lookup_query_variable(path, return_relation=is_rel_filter)
        is_optional_relation = False
        if not result:
            ident, target_class = self.build_traversal_from_path(
                {
                    "path": path,
                    "include_in_return": True,
                    "relation_filtering": is_rel_filter,
                },
                source_class,
            )
        else:
            ident, target_class, is_optional_relation = result
        return ident, path, prop, target_class, is_optional_relation

    def _finalize_filter_statement(
        self, operator: str, ident: str, prop: str, val: Any
    ) -> str:
        if operator in _UNARY_OPERATORS:
            # unary operators do not have a parameter
            statement = f"{ident}.{prop} {operator}"
        else:
            place_holder = self._register_place_holder(ident + "_" + prop)
            if operator == _SPECIAL_OPERATOR_ARRAY_IN:
                statement = operator.format(
                    ident=ident,
                    prop=prop,
                    val=f"${place_holder}",
                )
            else:
                statement = f"{ident}.{prop} {operator} ${place_holder}"
            self._query_params[place_holder] = val

        return statement

    def _build_filter_statements(
        self,
        ident: str,
        filters: dict[str, tuple],
        target: list[tuple[str, bool]],
        source_class: type[StructuredNode],
    ) -> None:
        for prop, op_and_val in filters.items():
            path = None
            is_rel_filter = "|" in prop
            target_class = source_class
            is_optional_relation = False
            if "__" in prop or is_rel_filter:
                (
                    ident,
                    path,
                    prop,
                    target_class,
                    is_optional_relation,
                ) = self._parse_path(source_class, prop)
            operator, val = op_and_val
            if not is_rel_filter:
                prop = target_class.defined_properties(rels=False)[
                    prop
                ].get_db_property_name(prop)
            statement = self._finalize_filter_statement(operator, ident, prop, val)
            target.append((statement, is_optional_relation))

    def _parse_q_filters(
        self, ident: str, q: Union[QBase, Any], source_class: type[StructuredNode]
    ) -> tuple[str, str]:
        target: list[tuple[str, bool]] = []

        def add_to_target(statement: str, connector: Q, optional: bool) -> None:
            if not statement:
                return
            if connector == Q.OR:
                statement = f"({statement})"
            target.append((statement, optional))

        for child in q.children:
            if isinstance(child, QBase):
                q_childs, q_opt_childs = self._parse_q_filters(
                    ident, child, source_class
                )
                add_to_target(q_childs, child.connector, False)
                add_to_target(q_opt_childs, child.connector, True)
            else:
                kwargs = {child[0]: child[1]}
                filters = process_filter_args(source_class, kwargs)
                self._build_filter_statements(ident, filters, target, source_class)
        match_filters = [filter[0] for filter in target if not filter[1]]
        opt_match_filters = [filter[0] for filter in target if filter[1]]
        if q.connector == Q.OR and match_filters and opt_match_filters:
            raise ValueError(
                "Cannot filter using OR operator on variables coming from both MATCH and OPTIONAL MATCH statements"
            )
        ret = f" {q.connector} ".join(match_filters)
        if ret and q.negated:
            ret = f"NOT ({ret})"
        opt_ret = f" {q.connector} ".join(opt_match_filters)
        if opt_ret and q.negated:
            opt_ret = f"NOT ({opt_ret})"
        return ret, opt_ret

    def build_where_stmt(
        self,
        ident: str,
        filters: list,
        source_class: type[StructuredNode],
        q_filters: Union[QBase, Any, None] = None,
    ) -> None:
        """
        Construct a where statement from some filters.

        We make a difference between filters applied to variables coming from MATCH and
        OPTIONAL MATCH statements.

        """
        if q_filters is not None:
            stmt, opt_stmt = self._parse_q_filters(ident, q_filters, source_class)
            if stmt:
                self._ast.where.append(stmt)
            if opt_stmt:
                self._ast.optional_where.append(opt_stmt)
        else:
            stmts = []
            for row in filters:
                negate = False

                # pre-process NOT cases as they are nested dicts
                if "__NOT__" in row and len(row) == 1:
                    negate = True
                    row = row["__NOT__"]

                for prop, operator_and_val in row.items():
                    operator, val = operator_and_val
                    if operator in _UNARY_OPERATORS:
                        # unary operators do not have a parameter
                        statement = (
                            f"{'NOT' if negate else ''} {ident}.{prop} {operator}"
                        )
                    else:
                        place_holder = self._register_place_holder(ident + "_" + prop)
                        statement = f"{'NOT' if negate else ''} {ident}.{prop} {operator} ${place_holder}"
                        self._query_params[place_holder] = val
                    stmts.append(statement)

            self._ast.where.append(" AND ".join(stmts))

    def lookup_query_variable(
        self, path: str, return_relation: bool = False
    ) -> TOptional[Tuple[str, Any, bool]]:
        """Retrieve the variable name generated internally for the given traversal path."""
        subgraph = self._ast.subgraph
        if not subgraph:
            return None
        traversals = re.split(path_split_regex, path)
        if len(traversals) == 0:
            raise ValueError("Can only lookup traversal variables")
        if traversals[0] not in subgraph:
            return None

        # Check if relation is coming from an optional MATCH
        # (declared using fetch|traverse_relations)
        is_optional_relation = False
        for relation in self.node_set.relations_to_fetch:
            if relation["path"] == path:
                is_optional_relation = relation.get("optional", False)
                break

        subgraph = subgraph[traversals[0]]
        if len(traversals) == 1:
            variable_to_return = f"{subgraph['rel_variable_name' if return_relation else 'variable_name']}"
            return variable_to_return, subgraph["target"], is_optional_relation
        variable_to_return = ""
        last_property = traversals[-1]
        for part in traversals[1:]:
            child = subgraph["children"].get(part)
            if not child:
                return None
            subgraph = child
            if part == last_property:
                # if last part of prop is the last traversal
                # we are safe to lookup the variable from the query
                variable_to_return = f"{subgraph['rel_variable_name' if return_relation else 'variable_name']}"
        return variable_to_return, subgraph["target"], is_optional_relation

    def build_query(self) -> str:
        query: str = ""

        if self._ast.lookup:
            query += self._ast.lookup

        # Instead of using only one MATCH statement for every relation
        # to follow, we use one MATCH per relation (to avoid cartesian
        # product issues...).
        # There might be optimizations to be done, using projections,
        # or pusing patterns instead of a chain of OPTIONAL MATCH.
        if self._ast.match:
            query += " MATCH "
            query += " MATCH ".join(i for i in self._ast.match)

        if self._ast.where:
            query += " WHERE "
            query += " AND ".join(self._ast.where)

        if self._ast.optional_match:
            query += " OPTIONAL MATCH "
            query += " OPTIONAL MATCH ".join(i for i in self._ast.optional_match)

        if self._ast.optional_where:
            # Make sure filtering works as expected with optional match, even if it's not performant...
            query += " WITH *"
            query += " WHERE "
            query += " AND ".join(self._ast.optional_where)

        if self._ast.with_clause:
            query += " WITH "
            query += self._ast.with_clause

        returned_items: list[str] = []
        if hasattr(self.node_set, "_intermediate_transforms"):
            for transform in self.node_set._intermediate_transforms:
                query += " WITH "
                query += "DISTINCT " if transform.get("distinct") else ""
                injected_vars: list = []
                # Reset return list since we'll probably invalidate most variables
                self._ast.return_clause = ""
                self._ast.additional_return = []
                for name, varprops in transform["vars"].items():
                    source = varprops["source"]
                    if isinstance(source, (NodeNameResolver, RelationNameResolver)):
                        transformation = source.resolve(self)
                    else:
                        transformation = source
                    if varprops.get("source_prop"):
                        transformation += f".{varprops['source_prop']}"
                    transformation += f" AS {name}"
                    if varprops.get("include_in_return"):
                        returned_items += [name]
                    injected_vars.append(transformation)
                query += ",".join(injected_vars)
                if not transform["ordering"]:
                    continue
                query += " ORDER BY "
                ordering: list = []
                for item in transform["ordering"]:
                    if isinstance(item, RawCypher):
                        ordering.append(item.render({}))
                        continue
                    if item.startswith("-"):
                        ordering.append(f"{item[1:]} DESC")
                    else:
                        ordering.append(item)
                query += ",".join(ordering)

        if hasattr(self.node_set, "_subqueries"):
            for subquery in self.node_set._subqueries:
                query += " CALL {"
                if subquery["initial_context"]:
                    query += " WITH "
                    context: list[str] = []
                    for var in subquery["initial_context"]:
                        if isinstance(var, (NodeNameResolver, RelationNameResolver)):
                            context.append(var.resolve(self))
                        else:
                            context.append(var)
                    query += ",".join(context)

                query += f"{subquery['query']} }} "
                self._query_params.update(subquery["query_params"])
                for varname in subquery["return_set"]:
                    # We declare the returned variables as "virtual" relations of the
                    # root node class to make sure they will be translated by a call to
                    # resolve_subgraph() (otherwise, they will be lost).
                    # This is probably a temporary solution until we find something better...
                    self._ast.subgraph[varname] = {
                        "target": None,  # We don't need target class in this use case
                        "children": {},
                        "variable_name": varname,
                        "rel_variable_name": varname,
                    }
                returned_items += subquery["return_set"]

        query += " RETURN "
        if self._ast.return_clause and not self._subquery_namespace:
            returned_items.append(self._ast.return_clause)
        if self._ast.additional_return:
            returned_items += self._ast.additional_return
        if hasattr(self.node_set, "_extra_results"):
            for props in self.node_set._extra_results:
                leftpart = props["vardef"].render(self)
                varname = (
                    props["alias"]
                    if props.get("alias")
                    else props["vardef"].get_internal_name()
                )
                if varname in returned_items:
                    # We're about to override an existing variable, delete it first to
                    # avoid duplicate error
                    returned_items.remove(varname)
                returned_items.append(f"{leftpart} AS {varname}")

        query += ", ".join(returned_items)

        if self._ast.order_by:
            query += " ORDER BY "
            query += ", ".join(self._ast.order_by)

        # If we return a count with pagination, pagination has to happen before RETURN
        # It will then be included in the WITH clause already
        if self._ast.skip and not self._ast.is_count:
            query += f" SKIP {self._ast.skip}"

        if self._ast.limit and not self._ast.is_count:
            query += f" LIMIT {self._ast.limit}"

        return query

    def _count(self) -> int:
        self._ast.is_count = True
        # If we return a count with pagination, pagination has to happen before RETURN
        # Like : WITH my_var SKIP 10 LIMIT 10 RETURN count(my_var)
        self._ast.with_clause = f"{self._ast.return_clause}"
        if self._ast.skip:
            self._ast.with_clause += f" SKIP {self._ast.skip}"

        if self._ast.limit:
            self._ast.with_clause += f" LIMIT {self._ast.limit}"

        self._ast.return_clause = f"count({self._ast.return_clause})"
        # drop order_by, results in an invalid query
        self._ast.order_by = None
        # drop additional_return to avoid unexpected result
        self._ast.additional_return = None
        query = self.build_query()
        results, _ = db.cypher_query(query, self._query_params)
        return int(results[0][0])

    def _contains(self, node_element_id: TOptional[Union[str, int]]) -> bool:
        # inject id = into ast
        if not self._ast.return_clause and self._ast.additional_return:
            self._ast.return_clause = self._ast.additional_return[0]
        if not self._ast.return_clause:
            raise ValueError("Cannot use contains without a return clause")
        ident = self._ast.return_clause
        place_holder = self._register_place_holder(ident + "_contains")
        self._ast.where.append(f"{db.get_id_method()}({ident}) = ${place_holder}")
        self._query_params[place_holder] = node_element_id
        return self._count() >= 1

    def _execute(self, lazy: bool = False, dict_output: bool = False) -> Any:
        if lazy:
            # inject id() into return or return_set
            if self._ast.return_clause:
                self._ast.return_clause = (
                    f"{db.get_id_method()}({self._ast.return_clause})"
                )
            else:
                if self._ast.additional_return is not None:
                    self._ast.additional_return = [
                        f"{db.get_id_method()}({item})"
                        for item in self._ast.additional_return
                    ]
        query = self.build_query()
        results, prop_names = db.cypher_query(
            query,
            self._query_params,
            resolve_objects=True,
        )
        if dict_output:
            for item in results:
                yield dict(zip(prop_names, item))
            return
        # The following is not as elegant as it could be but had to be copied from the
        # version prior to cypher_query with the resolve_objects capability.
        # It seems that certain calls are only supposed to be focusing to the first
        # result item returned (?)
        if results and len(results[0]) == 1:
            for n in results:
                yield n[0]
        else:
            for result in results:
                yield result


class BaseSet:
    """
    Base class for all node sets.

    Contains common python magic methods, __len__, __contains__ etc
    """

    query_cls = QueryBuilder
    source_class: type[StructuredNode]

    def all(self, lazy: bool = False) -> list:
        """
        Return all nodes belonging to the set
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :return: list of nodes
        :rtype: list
        """
        ast = self.query_cls(self).build_ast()
        results = [
            node for node in ast._execute(lazy)
        ]  # Collect all nodes asynchronously
        return results

    def __iter__(self) -> Iterator:
        ast = self.query_cls(self).build_ast()
        for item in ast._execute():
            yield item

    def __len__(self) -> int:
        ast = self.query_cls(self).build_ast()
        return ast._count()

    def __bool__(self) -> bool:
        """
        Override for __bool__ dunder method.
        :return: True if the set contains any nodes, False otherwise
        :rtype: bool
        """
        ast = self.query_cls(self).build_ast()
        _count = ast._count()
        return _count > 0

    def __nonzero__(self) -> bool:
        """
        Override for __bool__ dunder method.
        :return: True if the set contains any node, False otherwise
        :rtype: bool
        """
        return self.__bool__()

    def __contains__(self, obj: Union[StructuredNode, Any]) -> bool:
        if isinstance(obj, StructuredNode):
            if hasattr(obj, "element_id") and obj.element_id is not None:
                ast = self.query_cls(self).build_ast()
                obj_element_id = db.parse_element_id(obj.element_id)
                return ast._contains(obj_element_id)
            raise ValueError("Unsaved node: " + repr(obj))

        raise ValueError("Expecting StructuredNode instance")

    def __getitem__(self, key: Union[int, slice]) -> TOptional["BaseSet"]:
        if isinstance(key, slice):
            if key.stop and key.start:
                self.limit = key.stop - key.start
                self.skip = key.start
            elif key.stop:
                self.limit = key.stop
            elif key.start:
                self.skip = key.start

            return self

        if isinstance(key, int):
            self.skip = key
            self.limit = 1

            ast = self.query_cls(self).build_ast()
            _first_item = [node for node in ast._execute()][0]
            return _first_item

        return None


@dataclass
class Optional:  # type: ignore[no-redef]
    """Simple relation qualifier."""

    relation: str


@dataclass
class RelationNameResolver:
    """Helper to refer to a relation variable name.

    Since variable names are generated automatically within MATCH statements (for
    anything injected using fetch_relations or traverse_relations), we need a way to
    retrieve them.

    """

    relation: str

    def resolve(self, qbuilder: QueryBuilder) -> str:
        result = qbuilder.lookup_query_variable(self.relation, True)
        if result is None:
            raise ValueError(
                f"Unable to resolve variable name for relation {self.relation}"
            )
        return result[0]


@dataclass
class NodeNameResolver:
    """Helper to refer to a node variable name.

    Since variable names are generated automatically within MATCH statements (for
    anything injected using fetch_relations or traverse_relations), we need a way to
    retrieve them.

    """

    node: str

    def resolve(self, qbuilder: QueryBuilder) -> str:
        if self.node == "self" and qbuilder._ast.return_clause:
            return qbuilder._ast.return_clause
        result = qbuilder.lookup_query_variable(self.node)
        if result is None:
            raise ValueError(f"Unable to resolve variable name for node {self.node}")
        return result[0]


@dataclass
class BaseFunction:
    input_name: Union[str, "BaseFunction", NodeNameResolver, RelationNameResolver]

    def __post_init__(self) -> None:
        self._internal_name: str = ""

    def get_internal_name(self) -> str:
        return self._internal_name

    def resolve_internal_name(self, qbuilder: QueryBuilder) -> str:
        if isinstance(self.input_name, (NodeNameResolver, RelationNameResolver)):
            self._internal_name = self.input_name.resolve(qbuilder)
        else:
            self._internal_name = str(self.input_name)
        return self._internal_name

    def render(self, qbuilder: QueryBuilder) -> str:
        raise NotImplementedError


@dataclass
class AggregatingFunction(BaseFunction):
    """Base aggregating function class."""

    pass


@dataclass
class Collect(AggregatingFunction):
    """collect() function."""

    distinct: bool = False

    def render(self, qbuilder: QueryBuilder) -> str:
        varname = self.resolve_internal_name(qbuilder)
        if self.distinct:
            return f"collect(DISTINCT {varname})"
        return f"collect({varname})"


@dataclass
class ScalarFunction(BaseFunction):
    """Base scalar function class."""

    @property
    def function_name(self) -> str:
        raise NotImplementedError

    def render(self, qbuilder: QueryBuilder) -> str:
        if isinstance(self.input_name, str):
            content = str(self.input_name)
        elif isinstance(self.input_name, BaseFunction):
            content = self.input_name.render(qbuilder)
            self._internal_name = self.input_name.get_internal_name()
        else:
            content = self.resolve_internal_name(qbuilder)
        return f"{self.function_name}({content})"


@dataclass
class Last(ScalarFunction):
    """last() function."""

    @property
    def function_name(self) -> str:
        return "last"


@dataclass
class Size(ScalarFunction):
    """size() function."""

    @property
    def function_name(self) -> str:
        return "size"


@dataclass
class RawCypher:
    """Helper to inject raw cypher statement.

    Can be used in order_by() call for example.

    """

    statement: str

    def __post_init__(self) -> None:
        if CYPHER_ACTIONS_WITH_SIDE_EFFECT_EXPR.search(self.statement):
            raise ValueError(
                "RawCypher: Do not include any action that has side effect"
            )

    def render(self, context: dict) -> str:
        return string.Template(self.statement).substitute(context)


class NodeSet(BaseSet):
    """
    A class representing as set of nodes matching common query parameters
    """

    def __init__(self, source: Any) -> None:
        self.source = source  # could be a Traverse object or a node class
        if isinstance(source, Traversal):
            self.source_class = source.target_class
        elif inspect.isclass(source) and issubclass(source, StructuredNode):
            self.source_class = source
        elif isinstance(source, StructuredNode):
            self.source_class = source.__class__
        else:
            raise ValueError("Bad source for nodeset " + repr(source))

        # setup Traversal objects using relationship definitions
        install_traversals(self.source_class, self)

        self.filters: list = []
        self.q_filters = Q()
        self.order_by_elements: list = []

        # used by has()
        self.must_match: dict = {}
        self.dont_match: dict = {}

        self.relations_to_fetch: list = []
        self._extra_results: list = []
        self._subqueries: list[Subquery] = []
        self._intermediate_transforms: list = []

    def __await__(self) -> Any:
        return self.all().__await__()  # type: ignore[attr-defined]

    def _get(
        self, limit: TOptional[int] = None, lazy: bool = False, **kwargs: dict[str, Any]
    ) -> list:
        self.filter(**kwargs)
        if limit:
            self.limit = limit
        ast = self.query_cls(self).build_ast()
        results = [node for node in ast._execute(lazy)]
        return results

    def get(self, lazy: bool = False, **kwargs: Any) -> Any:
        """
        Retrieve one node from the set matching supplied parameters
        :param lazy: False by default, specify True to get nodes with id only without the parameters.
        :param kwargs: same syntax as `filter()`
        :return: node
        """
        result = self._get(limit=2, lazy=lazy, **kwargs)
        if len(result) > 1:
            raise MultipleNodesReturned(repr(kwargs))
        if not result:
            raise self.source_class.DoesNotExist(repr(kwargs))
        return result[0]

    def get_or_none(self, **kwargs: Any) -> Any:
        """
        Retrieve a node from the set matching supplied parameters or return none

        :param kwargs: same syntax as `filter()`
        :return: node or none
        """
        try:
            return self.get(**kwargs)
        except self.source_class.DoesNotExist:
            return None

    def first(self, **kwargs: Any) -> Any:
        """
        Retrieve the first node from the set matching supplied parameters

        :param kwargs: same syntax as `filter()`
        :return: node
        """
        result = self._get(limit=1, **kwargs)
        if result:
            return result[0]
        else:
            raise self.source_class.DoesNotExist(repr(kwargs))

    def first_or_none(self, **kwargs: Any) -> Any:
        """
        Retrieve the first node from the set matching supplied parameters or return none

        :param kwargs: same syntax as `filter()`
        :return: node or none
        """
        try:
            return self.first(**kwargs)
        except self.source_class.DoesNotExist:
            pass
        return None

    def filter(self, *args: Any, **kwargs: Any) -> "BaseSet":
        """
        Apply filters to the existing nodes in the set.

        :param args: a Q object

            e.g `.filter(Q(salary__lt=10000) | Q(salary__gt=20000))`.

        :param kwargs: filter parameters

            Filters mimic Django's syntax with the double '__' to separate field and operators.

            e.g `.filter(salary__gt=20000)` results in `salary > 20000`.

            The following operators are available:

             * 'lt': less than
             * 'gt': greater than
             * 'lte': less than or equal to
             * 'gte': greater than or equal to
             * 'ne': not equal to
             * 'in': matches one of list (or tuple)
             * 'isnull': is null
             * 'regex': matches supplied regex (neo4j regex format)
             * 'exact': exactly match string (just '=')
             * 'iexact': case insensitive match string
             * 'contains': contains string
             * 'icontains': case insensitive contains
             * 'startswith': string starts with
             * 'istartswith': case insensitive string starts with
             * 'endswith': string ends with
             * 'iendswith': case insensitive string ends with

        :return: self
        """
        if args or kwargs:
            self.q_filters = Q(self.q_filters & Q(*args, **kwargs))
        return self

    def exclude(self, *args: Any, **kwargs: Any) -> "BaseSet":
        """
        Exclude nodes from the NodeSet via filters.

        :param kwargs: filter parameters see syntax for the filter method
        :return: self
        """
        if args or kwargs:
            self.q_filters = Q(self.q_filters & ~Q(*args, **kwargs))
        return self

    def has(self, **kwargs: Any) -> "BaseSet":
        must_match, dont_match = process_has_args(self.source_class, kwargs)
        self.must_match.update(must_match)
        self.dont_match.update(dont_match)
        return self

    def order_by(self, *props: Any) -> "BaseSet":
        """
        Order by properties. Prepend with minus to do descending. Pass None to
        remove ordering.
        """
        should_remove = len(props) == 1 and props[0] is None
        if not hasattr(self, "order_by_elements") or should_remove:
            self.order_by_elements = []
            if should_remove:
                return self
        if "?" in props:
            self.order_by_elements.append("?")
        else:
            for prop in props:
                if isinstance(prop, RawCypher):
                    self.order_by_elements.append(prop)
                    continue
                prop = prop.strip()
                if prop.startswith("-"):
                    prop = prop[1:]
                    desc = True
                else:
                    desc = False

                if prop in self.source_class.defined_properties(rels=False):
                    property_obj = getattr(self.source_class, prop)
                    if isinstance(property_obj, AliasProperty):
                        prop = property_obj.aliased_to()

                self.order_by_elements.append(prop + (" DESC" if desc else ""))

        return self

    def _register_relation_to_fetch(
        self,
        relation_def: Any,
        alias: TOptional[str] = None,
        include_in_return: bool = True,
    ) -> dict:
        if isinstance(relation_def, Optional):
            item = {"path": relation_def.relation, "optional": True}
        else:
            item = {"path": relation_def}
        item["include_in_return"] = include_in_return

        if alias:
            item["alias"] = alias
        return item

    def fetch_relations(self, *relation_names: tuple[str, ...]) -> "NodeSet":
        """Specify a set of relations to traverse and return."""
        relations = []
        for relation_name in relation_names:
            relations.append(self._register_relation_to_fetch(relation_name))
        self.relations_to_fetch = relations
        return self

    def traverse_relations(
        self, *relation_names: tuple[str, ...], **aliased_relation_names: dict
    ) -> "NodeSet":
        """Specify a set of relations to traverse only."""
        relations = []
        for relation_name in relation_names:
            relations.append(
                self._register_relation_to_fetch(relation_name, include_in_return=False)
            )
        for alias, relation_def in aliased_relation_names.items():
            relations.append(
                self._register_relation_to_fetch(
                    relation_def, alias, include_in_return=False
                )
            )

        self.relations_to_fetch = relations
        return self

    def annotate(self, *vars: tuple, **aliased_vars: tuple) -> "NodeSet":
        """Annotate node set results with extra variables."""

        def register_extra_var(
            vardef: Union[AggregatingFunction, ScalarFunction, Any],
            varname: Union[str, None] = None,
        ) -> None:
            if isinstance(vardef, (AggregatingFunction, ScalarFunction)):
                self._extra_results.append(
                    {"vardef": vardef, "alias": varname if varname else ""}
                )
            else:
                raise NotImplementedError

        for vardef in vars:
            register_extra_var(vardef)
        for varname, vardef in aliased_vars.items():
            register_extra_var(vardef, varname)

        return self

    def _to_subgraph(self, root_node: Any, other_nodes: Any, subgraph: dict) -> Any:
        """Recursive method to build root_node's relation graph from subgraph."""
        root_node._relations = {}
        for name, relation_def in subgraph.items():
            for var_name, node in other_nodes.items():
                if (
                    var_name
                    not in [
                        relation_def["variable_name"],
                        relation_def["rel_variable_name"],
                    ]
                    or node is None
                ):
                    continue
                if isinstance(node, list):
                    if len(node) > 0 and isinstance(node[0], StructuredRel):
                        name += "_relationship"
                    root_node._relations[name] = []
                    for item in node:
                        root_node._relations[name].append(
                            self._to_subgraph(
                                item, other_nodes, relation_def["children"]
                            )
                        )
                else:
                    if isinstance(node, StructuredRel):
                        name += "_relationship"
                    root_node._relations[name] = self._to_subgraph(
                        node, other_nodes, relation_def["children"]
                    )

        return root_node

    def resolve_subgraph(self) -> list:
        """
        Convert every result contained in this node set to a subgraph.

        By default, we receive results from neomodel as a list of
        nodes without the hierarchy. This method tries to rebuild this
        hierarchy without overriding anything in the node, that's why
        we use a dedicated property to store node's relations.

        """
        if (
            self.relations_to_fetch
            and not self.relations_to_fetch[0]["include_in_return"]
        ):
            raise NotImplementedError(
                "You cannot use traverse_relations() with resolve_subgraph(), use fetch_relations() instead."
            )
        results: list = []
        qbuilder = self.query_cls(self)
        qbuilder.build_ast()
        if not qbuilder._ast.subgraph:
            raise RuntimeError(
                "Nothing to resolve. Make sure to include relations in the result using fetch_relations() or filter()."
            )
        other_nodes = {}
        root_node = None
        for row in qbuilder._execute(dict_output=True):
            for name, node in row.items():
                if node.__class__ is self.source and "_" not in name:
                    root_node = node
                    continue
                if isinstance(node, list) and isinstance(node[0], list):
                    other_nodes[name] = node[0]
                    continue
                other_nodes[name] = node
            results.append(
                self._to_subgraph(root_node, other_nodes, qbuilder._ast.subgraph)
            )
        return results

    def subquery(
        self,
        nodeset: "NodeSet",
        return_set: list[str],
        initial_context: TOptional[list[str]] = None,
    ) -> "NodeSet":
        """Add a subquery to this node set.

        A subquery is a regular cypher query but executed within the context of a CALL
        statement. Such query will generally fetch additional variables which must be
        declared inside return_set variable in order to be included in the final RETURN
        statement.
        """
        namespace = f"sq{len(self._subqueries) + 1}"
        qbuilder = nodeset.query_cls(nodeset, subquery_namespace=namespace).build_ast()
        for var in return_set:
            if (
                var != qbuilder._ast.return_clause
                and (
                    not qbuilder._ast.additional_return
                    or var not in qbuilder._ast.additional_return
                )
                and var
                not in [res["alias"] for res in nodeset._extra_results if res["alias"]]
                and var
                not in [
                    varname
                    for tr in nodeset._intermediate_transforms
                    for varname, vardef in tr["vars"].items()
                    if vardef.get("include_in_return")
                ]
            ):
                raise RuntimeError(f"Variable '{var}' is not returned by subquery.")
        if initial_context:
            for var in initial_context:
                if type(var) is not str and not isinstance(
                    var, (NodeNameResolver, RelationNameResolver, RawCypher)
                ):
                    raise ValueError(
                        f"Wrong variable specified in initial context, should be a string or an instance of NodeNameResolver or RelationNameResolver"
                    )
        self._subqueries.append(
            {
                "query": qbuilder.build_query(),
                "query_params": qbuilder._query_params,
                "return_set": return_set,
                "initial_context": initial_context,
            }
        )
        return self

    def intermediate_transform(
        self,
        vars: dict[str, Transformation],
        distinct: bool = False,
        ordering: TOptional[list] = None,
    ) -> "NodeSet":
        if not vars:
            raise ValueError(
                "You must provide one variable at least when calling intermediate_transform()"
            )
        for name, props in vars.items():
            source = props["source"]
            if type(source) is not str and not isinstance(
                source, (NodeNameResolver, RelationNameResolver, RawCypher)
            ):
                raise ValueError(
                    f"Wrong source type specified for variable '{name}', should be a string or an instance of NodeNameResolver or RelationNameResolver"
                )
        self._intermediate_transforms.append(
            {"vars": vars, "distinct": distinct, "ordering": ordering}
        )
        return self


class Traversal(BaseSet):
    """
    Models a traversal from a node to another.

    :param source: Starting of the traversal.
    :type source: A :class:`~neomodel.core.StructuredNode` subclass, an
                  instance of such, a :class:`~neomodel.match.NodeSet` instance
                  or a :class:`~neomodel.match.Traversal` instance.
    :param name: A name for the traversal.
    :type name: :class:`str`
    :param definition: A relationship definition that most certainly deserves
                       a documentation here.
    :type definition: :class:`dict`
    """

    definition: dict
    source: Any
    source_class: Any
    target_class: Any
    name: str
    filters: list

    def __await__(self) -> Any:
        return self.all().__await__()  # type: ignore[attr-defined]

    def __init__(self, source: Any, name: str, definition: dict) -> None:
        """
        Create a traversal

        """
        self.source = source

        if isinstance(source, Traversal):
            self.source_class = source.target_class
        elif inspect.isclass(source) and issubclass(source, StructuredNode):
            self.source_class = source
        elif isinstance(source, StructuredNode):
            self.source_class = source.__class__
        elif isinstance(source, NodeSet):
            self.source_class = source.source_class
        else:
            raise TypeError(f"Bad source for traversal: {type(source)}")

        invalid_keys = set(definition) - {
            "direction",
            "model",
            "node_class",
            "relation_type",
        }
        if invalid_keys:
            raise ValueError(f"Prohibited keys in Traversal definition: {invalid_keys}")

        self.definition = definition
        self.target_class = definition["node_class"]
        self.name = name
        self.filters: list = []

    def match(self, **kwargs: Any) -> "Traversal":
        """
        Traverse relationships with properties matching the given parameters.

            e.g: `.match(price__lt=10)`

        :param kwargs: see `NodeSet.filter()` for syntax
        :return: self
        """
        if kwargs:
            if self.definition.get("model") is None:
                raise ValueError(
                    "match() with filter only available on relationships with a model"
                )
            output = process_filter_args(self.definition["model"], kwargs)
            if output:
                self.filters.append(output)
        return self
