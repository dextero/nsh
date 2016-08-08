from typing import Mapping, Generic, TypeVar

T = TypeVar('T')
S = TypeVar('S')

class OrderedMapping(Mapping[T, S]):
    pass
