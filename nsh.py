# coding=utf-8

import cmd
import time
import collections
import sys
import os
import inspect
import imp
from typing import Mapping

import powercmd

class NshMsg(object):
    def summary(self): raise NotImplementedError()
    def details(self): raise NotImplementedError()
    def to_test_case(self): raise NotImplementedError()

Cmd = collections.namedtuple('Cmd', ['cmd'])
Send = collections.namedtuple('Send', ['msg'])
Recv = collections.namedtuple('Recv', ['msg'])

class TempCwd(object):
    def __init__(self, new_cwd):
        self.new_cwd = new_cwd
        self.old_cwd = None

    def __enter__(self):
        self.old_cwd = os.getcwd()
        os.chdir(self.new_cwd)

    def __exit__(self, exc_type, exc_val, exc_traceback):
        os.chdir(self.old_cwd)

class NshCmds(object):
    def init(self): pass
    def cleanup(self): pass
    def try_read(self): pass

    def write_test_case_init(self, f): pass
    def write_test_case_cleanup(self, f): pass

class Nsh(powercmd.Cmd, NshCmds):
    def __init__(self, module):
        super(powercmd.Cmd, self).__init__()

        self.history = []
        self.curr_mod = '(none)'
        self.set_prompt('(none)')

        self.nsh_mod(module)

    def get_command_prefixes(self) -> Mapping[str, str]:
        prefixes = powercmd.Cmd.get_command_prefixes(self)
        prefixes.update({'nsh_': '/'})
        return prefixes

    def set_prompt(self, extra_text=None):
        extra_text = ' %s' % (extra_text,) if extra_text else ''
        self.prompt = '[%s]%s $ ' % (self.curr_mod, extra_text)

    def nsh_reset(self):
        "Clears command history."
        self.history = []

    def nsh_save(self,
                 filename: str='/tmp/nsh-save'):
        "Saves command history to a test case file."

        with open(filename, 'w') as f:
            self.write_test_case_init(f);

            for entry in self.history:
                if isinstance(entry, Cmd):
                    f.write('# %s\n' % (entry.cmd,))
                elif (isinstance(entry, Send)
                      or isinstance(entry, Recv)):
                    f.write(entry.msg.to_test_case(type(entry)))
                    f.write('\n')
                else:
                    print('unexpected history entry: %s' % (entry,))

            self.write_test_case_cleanup(f)

        print('saved to %s' % (filename,))

    def nsh_mod(self,
                mod_name: str):
        "Loads a specific protocol connector."

        print('loading module %s' % (mod_name,))
        mod_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'connectors')
        sys.path.insert(0, mod_path)
        try:
            mod = __import__(mod_name)
        finally:
            sys.path.pop(0)

        if not mod:
            raise powercmd.Cmd.CancelCmd('cannot load module: %s' % mod_name)
        self.curr_mod = mod_name

        bases = tuple([c for c in mod.__dict__.values()
                       if isinstance(c, type) and issubclass(c, NshCmds)])

        for base in bases:
            for name, member in base.__dict__.items():
                if name.startswith('do_'):
                    params = inspect.signature(member).parameters
                    args_list = list('%s: %s' % (name, p.annotation.__name__) for name, p in params.items())
                    args = ', '.join(args_list[1:])
                    print('  %s %s' % (name[3:], args))

        class NshSubclass(Nsh): pass
        NshSubclass.__bases__ += bases

        self.__class__ = NshSubclass
        self.init()

        self.set_prompt()

    def nsh_details(self,
                    idx: int=1):
        "Displays details of a recent message."

        for entry in reversed(self.history):
            if (isinstance(entry, Recv)
                    or isinstance(entry, Send)):
                idx -= 1
                if idx <= 0:
                    print('\n*** %s ***' % (entry.__class__.__name__))
                    print(entry.msg.details())
                    return

        print('message not found')

    def emptyline(self):
        while self.try_read():
            pass
