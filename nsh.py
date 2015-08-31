# coding=utf-8

import cmd
import time
import powercmd

class NshCmds(object):
    def init(self): pass
    def cleanup(self): pass
    def try_read(self): pass

class Nsh(powercmd.Cmd, NshCmds):
    def __init__(self, module):
        self.curr_mod = '(none)'
        self.set_prompt('(none)')

        self.do_load(module)

    def set_prompt(self, extra_text=None):
        extra_text = ' %s' % (extra_text,) if extra_text else ''
        self.prompt = '[%s]%s $ ' % (self.curr_mod, extra_text)

    def do_load(self,
                mod_name=(str, powercmd.Required)):
        "Loads a specific protocol connector."

        print('loading module %s' % (mod_name,))
        self.curr_mod = mod_name

        mod = __import__(mod_name)
        bases = tuple([c for c in mod.__dict__.values()
                       if isinstance(c, type) and issubclass(c, NshCmds)])

        for base in bases:
            for name, member in base.__dict__.items():
                if name.startswith('do_'):
                    args = ' '.join(inspect.getargspec(member)[0][1:])
                    print('  %s %s' % (name[3:], args))

        class NshSubclass(Nsh): pass
        NshSubclass.__bases__ += bases

        self.__class__ = NshSubclass
        self.init()

        self.set_prompt()

    def emptyline(self):
        msg = self.try_read()
        if msg:
            print(msg)
