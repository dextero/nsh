"""
powercmd - A generic class to build typesafe line-oriented command interpreters.
"""

import cmd
import collections
import copy
import inspect
import re
import shlex
import string
import sys
import traceback

from typing import Any, Callable, List, Mapping, Sequence
from powercmd.extra_typing import OrderedMapping

from powercmd.match_string import match_string
from powercmd.command_invocation import CommandInvocation

class Cmd(cmd.Cmd):
    """
    A simple framework for writing typesafe line-oriented command interpreters.
    """
    class SyntaxError(Exception):
        """An error raised if the input cannot be parsed as a valid command."""
        pass

    def __init__(self):
        super(cmd.Cmd, self).__init__()

        self._last_exception = None

    # pylint: disable=no-self-use
    def get_command_prefixes(self):
        """
        Returns a mapping {method_command_prefix -> input_string_prefix}.
        input_string_prefix is a prefix of a command typed in the command line,
        method_command_prefix is the prefix for a matching command.

        If this function returns {'do_': ''}, then all methods whose names start
        with 'do_' will be available as commands with the same names, i.e.
        typing 'foo' will execute 'do_foo'.
        If it returned {'do_', '!'}, then one has to type '!foo' in order to
        execute 'do_foo'.
        """
        return {'do_': ''}

    # pylint: disable=no-self-use
    def get_constructor(self,
                        annotation: Any) -> Callable[[str], Any]:
        """
        Returns a callable that parses a string and returns an object of an
        appropriate type defined by the ANNOTATION.
        """
        def ensure_callable(arg):
            """Raises an exception if the argument is not callable."""
            if not callable(arg):
                raise TypeError('invalid type: ' + repr(arg))
            return arg

        return {
            bytes: lambda text: bytes(text, 'ascii')
        }.get(annotation, ensure_callable(annotation))

    def do_get_error(self):
        """Displays an exception thrown by last command."""
        if self._last_exception is None:
            print('no errors')
        else:
            traceback.print_exception(*self._last_exception)

    def do_exit(self):
        """Terminates the command loop."""
        print('exiting')
        return True

    # pylint: disable=invalid-name
    def do_EOF(self):
        """Terminates the command loop."""
        print('')
        return self.do_exit()

    def do_help(self,
                topic: str=''):
        """Displays a description of given command."""
        all_handlers = self._get_all_commands()

        try:
            handler = self._choose_cmd_handler(all_handlers, topic)

            arg_spec = self._get_handler_params(handler)
            arg_spec.pop(0) # skip 'self'
            args_with_defaults = list((name, param.default) for name, param in arg_spec)

            print('usage: %s %s'
                  % (topic,
                     ' '.join('%s=%s' % (arg, repr(default))
                              if default is not inspect.Parameter.empty
                              else str(arg)
                              for arg, default in args_with_defaults)))
        except Cmd.SyntaxError:
            print('no such command: %s' % (topic,))
            print('available commands: %s' % (' '.join(sorted(all_handlers)),))

    def _construct_arg(self,
                       formal_param: inspect.Parameter,
                       value: str) -> Any:
        """
        Constructs an argument from string VALUE, with the type defined by an
        annotation to the FORMAL_PARAM.
        """
        ctor = self.get_constructor(formal_param.annotation)
        try:
            return ctor(value)
        except ValueError as e:
            raise Cmd.SyntaxError(e)

    def _construct_args(self,
                        formal: OrderedMapping[str, inspect.Parameter],
                        named_args: Mapping[str, str],
                        free_args: Sequence[str]):
        """
        Parses a list of actual call parameters by calling an appropriate
        constructor for each of them.
        """
        typed_args = {}
        extra_free = []

        for name, value in named_args.items():
            if name not in formal:
                print('unrecognized argument: %s' % (name,))
                extra_free.append('%s=%s' % (name, value))
            elif name in typed_args:
                raise Cmd.SyntaxError('duplicate value for argument: %s' % (name,))
            else:
                typed_args[name] = self._construct_arg(formal[name], value)

        typed_args = self._assign_free_args(formal, typed_args,
                                            free_args + extra_free)
        typed_args = Cmd._fill_default_args(formal, typed_args)
        return typed_args

    def _assign_free_args(self,
                          formal: OrderedMapping[str, inspect.Parameter],
                          actual: OrderedMapping[str, str],
                          free: Sequence[str]) -> Mapping[str, str]:
        """
        Returns the ACTUAL dict extended by initial FORMAL arguments matched to
        FREE values.
        """
        if len(free) > len(formal):
            raise Cmd.SyntaxError('too many free arguments: expected at most %d'
                                  % (len(formal),))

        result = copy.deepcopy(actual)
        for name, value in zip(formal, free):
            if name in result:
                raise Cmd.SyntaxError('cannot assign free argument to %s: '
                                      'argument already present' % (name,))

            result[name] = self._construct_arg(formal[name], value)

        return result

    @staticmethod
    def _fill_default_args(formal: Mapping[str, inspect.Parameter],
                           actual: Mapping[str, str]):
        """
        Returns the ACTUAL dict extended by default values of unassigned FORMAL
        parameters.
        """
        result = copy.deepcopy(actual)
        for name, param in formal.items():
            if (name not in result
                    and param.default is not inspect.Parameter.empty):
                result[name] = param.default

        return result

    def _complete_impl(self, line, possibilities):
        """
        Returns the list of possible tab-completions for given LINE.
        """
        words = line.split(' ')
        if words and '=' in words[-1] and line[-1] not in string.whitespace:
            try:
                key, val = words[-1].split('=', maxsplit=1)
                if len(possibilities[key]) > 0:
                    return match_string(val, possibilities[key], quiet=True)
            except ValueError:
                print('ValueError')

        matches = match_string(words[-1], possibilities, quiet=True)
        return [x + '=' for x in matches]

    # python3.5 implements completedefault arguments as *ignored
    # pylint: disable=arguments-differ,unused-argument
    def completedefault(self,
                        word_under_cursor: str,
                        line: str,
                        word_begidx: int,
                        word_endidx: int) -> List[str]:
        """
        Returns a list of possible tab-completions for currently typed command.
        """
        if re.match(r'^[^=]+=', word_under_cursor):
            # TODO: type-specific completion
            return

        command = shlex.split(line)[0]
        all_commands = self._get_all_commands()
        handler = self._choose_cmd_handler(all_commands, command, quiet=True)

        arg_spec = self._get_handler_params(handler)
        return self._complete_impl(line, arg_spec)

    def _get_all_commands(self) -> Mapping[str, Callable]:
        """Returns all defined commands."""
        import types

        def unbind(f):
            """
            Returns the base function if the argument is a bound one.
            https://bugs.python.org/msg166144
            """
            if not callable(f):
                raise TypeError('%s is not callable'  % (repr(f),))

            self = getattr(f, '__self__', None)
            if self is not None and not isinstance(self, types.ModuleType) \
                                and not isinstance(self, type):
                if hasattr(f, '__func__'):
                    return f.__func__
                return getattr(type(f.__self__), f.__name__)

            return f

        members = inspect.getmembers(self)
        prefixes = self.get_command_prefixes()
        commands = {}

        for name, handler in members:
            if not callable(handler):
                continue
            for prefix, substitution in prefixes.items():
                if name.startswith(prefix):
                    assert substitution + name not in commands
                    commands[substitution + name[len(prefix):]] = unbind(handler)

        return commands

    def _choose_cmd_handler(self,
                            cmds: Mapping[str, Callable],
                            short_cmd: str,
                            quiet: bool=False) -> Callable:
        """Returns a command handler that matches SHORT_CMD."""
        matches = match_string(short_cmd, cmds, quiet)

        if not matches:
            raise Cmd.SyntaxError('no such command: %s' % (short_cmd,))
        elif len(matches) > 1:
            raise Cmd.SyntaxError('ambigious command: %s (possible: %s)'
                                  % (short_cmd, ' '.join(matches)))
        else:
            return cmds[matches[0]]

    @staticmethod
    def _get_handler_params(handler: Callable) -> OrderedMapping[str, inspect.Parameter]:
        """Returns a list of command parameters for given HANDLER."""
        params = inspect.signature(handler).parameters
        params = collections.OrderedDict(list(params.items())[1:]) # drop 'self'
        return params

    def _execute_cmd(self,
                     command: CommandInvocation) -> Any:
        """Executes given COMMAND."""
        all_commands = self._get_all_commands()
        handler = self._choose_cmd_handler(all_commands, command.command)
        formal_params = self._get_handler_params(handler)
        typed_args = self._construct_args(formal_params,
                                          command.named_args, command.free_args)

        return handler(self, **typed_args)

    def default(self, cmdline):
        try:
            if not cmdline:
                return self.emptyline()

            return self._execute_cmd(CommandInvocation.from_cmdline(cmdline))
        except Exception as e:
            self._last_exception = sys.exc_info()
            print(e)
        else:
            self._last_exception = None

    def onecmd(self, cmdline):
        return self.default(cmdline)

    def cmdloop(self):
        try:
            cmd.Cmd.cmdloop(self)
        except KeyboardInterrupt:
            pass
