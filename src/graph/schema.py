from enum import Enum

class NodeType(str, Enum):
    FILE = "file"
    CHUNK = "chunk"

class EdgeType(str, Enum):
    IMPORTS = "imports"
    CONTAINS = "contains"
    INHERITS = "inherits"
    CALLS = "calls"