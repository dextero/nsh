# coding=utf-8

import cmd
import collections
import imp
import inspect
import os
import readline
import sys
import time
from typing import Mapping, List

import powercmd

class NshMsg(object):
    """
    A message sent to or received from the network.

    Stored in Nsh command history for later inspection or to generate a test
    case based on its contents.
    """

    def summary(self):
        """
        Returns a brief description of the message, preferably no longer than
        a single line.
        """
        raise NotImplementedError()

    def details(self):
        """
        Returns a detailed description of the message. The output of this
        function is displayed when a /details command is used.
        """
        raise NotImplementedError()

    def to_test_case(self, type):
        """
        Returns a string that will be saved as a test case when the /save
        command is used.

        TYPE is either nsh.Send (if the message was sent to the network) or
        nsh.Recv (if it was received).

        An example implementation might look like this:

            def to_test_case(self, type):
                if type is nsh.Recv:
                    return ('msg = receive_message()\n
                            'assertEqual(msg.id, %d)\n') % self.msg_id
                else:
                    return 'send_message(%s)\n' % repr(self)

        """
        raise NotImplementedError()

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
    """
    A class representing a specific protocol connector.

    Any methods whose names begin with 'do_' are considered command handlers.
    For details, see powercmd.Cmd documentation.
    """
    def init(self):
        """Called when a protocol connector is loaded."""
        pass
    def try_read(self):
        """
        Called after every command read from the user. Should return:
        - a NshMsg subclass representing a received message if received one,
        - None otherwise
        """
        pass

    def write_test_case_init(self, f):
        """
        Used to write a test case header in /save command handler. F is a
        writable file-like object.
        """
        pass
    def write_test_case_cleanup(self, f):
        """
        Used to write a test case footer in /save command handler. F is a
        writable file-like object.
        """
        pass

NSH_HISTORY_FILE = os.path.join(os.path.expanduser('~'), '.nsh_history')

class Nsh(powercmd.Cmd, NshCmds):
    def __init__(self, module):
        super(powercmd.Cmd, self).__init__()

        self.history = []
        self.curr_mod = '(none)'
        self.set_prompt('(none)')

        self.nsh_mod(module)

        try:
            readline.read_history_file(NSH_HISTORY_FILE)
        except FileNotFoundError:
            pass

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
        """
        Generates a test case file based on the command history.

        The history is stored in `self.history` list. It may contain elements
        of following types:
        - nsh.Cmd - a command invocation, typed by the user,
        - nsh.Send - a message sent by a current connector. The `msg` member
                     of this class should be an instance of NshMsg subclass,
        - nsh.Recv - a message returned from the `try_read` method of NshCmds
                     subclass, wrapped into `nsh.Recv` type. The internal `msg`
                     should be an instance of NsgMsg subclass.
        Any other element types are considered invalid and will be ignored.

        Test case header and footer can be generated using
        `write_test_case_init` and `write_test_case_cleanup` methods of the
        NshCmds subclass.

        The test case body is generated by saving each history entry to a python
        script in a following manner:
        - nsh.Cmd instances are inserted as comments
        - for nsh.Send and nsh.Recv the result of calling `to_test_case(TYPE)`
          is saved to the test case file. TYPE is nsh.Send or nsh.Recv,
          depending on the wrapper.
        """

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

    @staticmethod
    def list_connectors() -> List[str]:
        connectors = []

        mod_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'connectors')
        sys.path.insert(0, mod_path)

        for filename in os.listdir(mod_path):
            if not filename.endswith('.py'):
                continue

            filename = filename[:-3]
            try:
                mod = __import__(filename)
                if any(isinstance(x, type) and issubclass(x, NshCmds)
                        for x in mod.__dict__.values()):
                    connectors.append(filename)
            except:
                pass

        sys.path.pop(0)
        return connectors

    def nsh_mod(self,
                mod_name: str):
        """
        Loads a specific protocol connector.

        A connector is a python source file contained inside the connectors/
        subdirectory that exports at least one subclass of the NshCmds class.
        """

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
        """
        Displays details of a recent message.

        Examples:
            /details     - display last message
            /details NUM - display NUM-th last message
        """

        for entry in reversed(self.history):
            if (isinstance(entry, Recv)
                    or isinstance(entry, Send)):
                idx -= 1
                if idx <= 0:
                    print('\n*** %s ***' % (entry.__class__.__name__))
                    print(entry.msg.details())
                    return

        print('message not found')

    def onecmd(self, cmdline):
        result = self.default(cmdline)
        readline.write_history_file(NSH_HISTORY_FILE)
        return result

    def emptyline(self):
        while self.try_read():
            pass
