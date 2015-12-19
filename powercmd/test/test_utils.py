import collections

from typing import Callable

ProxyCall = object()
MockCall = collections.namedtuple('Call', ['args', 'retval'])

class CallWrapper(object):
    def __init__(self,
                 fn: Callable):
        self.fn = fn
        self.calls = []

    def __enter__(self):
        pass
    def __exit__(self, *exc):
        if len(self.calls) != 0:
            raise AssertionError('%d more calls expected' % len(self.calls))

    def expect_no_calls(self):
        return self

    def expect_call(self, **kwargs):
        self.calls.insert(0, MockCall(kwargs, ProxyCall))
        return self

    def returning(self, retval):
        self.calls[0].retval = retval
        return self

    def __call__(self, _self, **kwargs):
        call = self.calls.pop(0)

        if call.args != kwargs:
            raise AssertionError('expected call with %s, got %s'
                                 % (repr(call.args), repr(kwargs)))
        if call.retval is ProxyCall:
            return self.fn(_self, **kwargs)
        else:
            return call.retval

    def __str__(self):
        def stringify_call(call):
            return ('call: %s -> %s'
                    % (' '.join('='.join((k, repr(v)))
                                for k, v in call.args.items()),
                       '<proxy call>' if call.retval is ProxyCall else repr(call.retval)))

        return ('%d calls:\n%s'
                % (len(self.call_kwargs),
                   '\n'.join(stringify_call(call) for call in self.calls)))

def mock(fn):
    return CallWrapper(fn)

