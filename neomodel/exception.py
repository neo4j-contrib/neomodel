class DatabaseNotInDebugMode(Exception):
    def __init__(self, msg):
        super().__init__(self, msg)

# Back compat
from .exceptions import *