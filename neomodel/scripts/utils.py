import sys
from importlib import import_module
from os import path


def load_python_module_or_file(name):
    """
    Imports an existing python module or file into the current workspace.

    In both cases, *the resource must exist*.

    :param name: A string that refers either to a Python module or a source coe
                 file to load in the current workspace.
    :type name: str
    """
    # Is a file
    if name.lower().endswith(".py"):
        basedir = path.dirname(path.abspath(name))
        # Add base directory to pythonpath
        sys.path.append(basedir)
        module_name = path.basename(name)[:-3]

    else:  # A module
        # Add current directory to pythonpath
        sys.path.append(path.abspath(path.curdir))

        module_name = name

    if module_name.startswith("."):
        pkg = module_name.split(".")[1]
    else:
        pkg = None

    import_module(module_name, package=pkg)
    print(f"Loaded {name}")


def recursive_list_classes(cls, exclude_list=None):  # recursively return all subclasses
    subclasses = cls.__subclasses__()
    if not subclasses:  # base case: no more subclasses
        return []
    elif cls not in exclude_list:
        return [s for s in subclasses if s not in exclude_list] + [
            g
            for s in cls.__subclasses__()
            for g in recursive_list_classes(s, exclude_list=exclude_list)
        ]
