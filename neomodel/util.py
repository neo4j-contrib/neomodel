import warnings

OUTGOING, INCOMING, EITHER = 1, -1, 0


def deprecated(message):
    # pylint:disable=invalid-name
    def f__(f):
        def f_(*args, **kwargs):
            warnings.warn(message, category=DeprecationWarning, stacklevel=2)
            return f(*args, **kwargs)

        f_.__name__ = f.__name__
        f_.__doc__ = f.__doc__
        f_.__dict__.update(f.__dict__)
        return f_

    return f__


def classproperty(f):
    class cpf:
        def __init__(self, getter):
            self.getter = getter

        def __get__(self, obj, type=None):
            return self.getter(type)

    return cpf(f)


# Just used for error messages
class _UnsavedNode:
    def __repr__(self):
        return "<unsaved node>"

    def __str__(self):
        return self.__repr__()


def get_graph_entity_properties(entity):
    """
    Get the properties from a neo4j.graph.Entity (neo4j.graph.Node or neo4j.graph.Relationship) object.
    """
    return entity._properties


def enumerate_traceback(initial_frame):
    depth, frame = 0, initial_frame
    while frame is not None:
        yield depth, frame
        frame = frame.f_back
        depth += 1


def version_tag_to_integer(version_tag):
    """
    Converts a version string to an integer representation to allow for quick comparisons between versions.

    :param a_version_string: The version string to be converted (e.g. '5.4.0')
    :type a_version_string: str
    :return: An integer representation of the version string (e.g. '5.4.0' --> 50400)
    :rtype: int
    """
    components = version_tag.split(".")
    while len(components) < 3:
        components.append("0")
    num = 0
    for index, component in enumerate(components):
        # Aura started adding a -aura suffix in version numbers, like "5.14-aura"
        # This will strip the suffix to allow for proper comparison : 14 instead of 14-aura
        if "-" in component:
            component = component.split("-")[0]
        num += (100 ** ((len(components) - 1) - index)) * int(component)
    return num
