_DELIMITERS = {
    '(': ')',
    '[': ']',
    '{': '}',
    '"': '"',
    "'": "'",
}

def split_list(text: str,
               separator: str=','):
    if len(separator) != 1:
        raise ValueError('only single-character separators are supported')
    if separator in _DELIMITERS:
        raise ValueError('delimiters: %s are not supported'
                         % (''.join(_DELIMITERS),))

    stack = []
    escape = False
    start = 0

    for idx, c in enumerate(text):
        if stack:
            if stack[-1] == c:
                stack.pop()
        elif c in _DELIMITERS:
            stack.append(_DELIMITERS[c])
        elif c == separator:
            yield text[start:idx]
            start = idx + 1

    if stack:
        raise ValueError('text contains unmatched delimiters: %s (text = %s)'
                         % (''.join(stack), text))

    yield text[start:]
