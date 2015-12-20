import collections
import re
import shlex

from typing import Sequence
from powercmd.extra_typing import OrderedMapping

class CommandInvocation(object):
    def __init__(self,
                 command: str,
                 named_args: OrderedMapping[str, str]=None,
                 free_args: Sequence[str]=None):
        self.command = command
        self.named_args = named_args or collections.OrderedDict()
        self.free_args = free_args or []

    def __eq__(self, other):
        return ((self.command, self.named_args, self.free_args)
                == (other.command, other.named_args, other.free_args))

    def __str__(self):
        return ('command = %s\nnamed_args (%d):\n%s\nfree_args (%d):\n%s'
                % (self.command,
                   len(self.named_args),
                   '\n'.join('  %s=%s' % kv for kv in self.named_args.items()),
                   len(self.free_args),
                   '\n'.join('  %s' % x for x in self.free_args)))

    def __repr__(self):
        return ('CommandInvocation(command=%s,named_args=%s,free_args=%s)'
                % (repr(self.command), repr(self.named_args), repr(self.free_args)))

    @staticmethod
    def from_cmdline(cmdline: str):
        words = shlex.split(cmdline)
        if not words:
            return CommandInvocation(command='')

        command = words[0]
        named_args = collections.OrderedDict()
        free_args = []

        for word in words[1:]:
            if re.match(r'^[a-zA-Z0-9_]+=', word):
                name, value = word.split('=', maxsplit=1)
                if name in named_args:
                    raise Cmd.CancelCmd('multiple values for key: %s' % (name,))
                else:
                    named_args[name] = value
            else:
                free_args.append(word)

        return CommandInvocation(command, named_args, free_args)
