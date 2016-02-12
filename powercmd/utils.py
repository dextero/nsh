from typing import List

def get_available_instance_names(cls: type,
                                 match_extra_cls: List[type]=None,
                                 append_paren_to_callables=False):
    """
    Returns a list of member names that are either CLS or any of the types
    specified in the MATCH_EXTRA_CLS.

    If APPEND_PAREN_TO_CALLABLES is True, returned names that are callable
    will be suffixed by the '(' character.
    """
    def get_suffix(value):
        return '(' if append_paren_to_callables and callable(value) else ''

    valid_classes = [cls] + (match_extra_cls or [])
    return (name + get_suffix(value) for name, value in cls.__dict__.items()
            if any(isinstance(value, c) for c in valid_classes))

def match_instance(cls: type,
                   text: str,
                   match_extra_cls: List[type]=None):
    """
    Finds instances of one of CLS or any of TARGET_CLS types among attributes
    of the CLS.
    """
    try:
        inst = getattr(cls, text)

        if any(isinstance(inst, c) for c in [cls] + (match_extra_cls or [])):
            return inst
    except AttributeError:
        pass

    raise ValueError('%s is not a valid instance of %s' % (text, cls.__name__))
