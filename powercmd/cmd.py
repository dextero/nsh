import cmd
import collections
import copy
import inspect
import re
import shlex
import string

from typing import Any, Callable, Mapping, Sequence
from extra_typing import OrderedMapping

class Cmd(cmd.Cmd):
    class CancelCmd(Exception):
        pass

    def do_exit(self):
        print('exiting')
        return True

    def do_EOF(self):
        print('')
        return self.do_exit()

    def get_constructor(self,
                        annotation: Any) -> Callable[[str], Any]:
        """
        Returns a callable that parses a string and returns an object of an
        appropriate type.
        """
        def ensure_callable(x):
            if not callable(x):
                raise TypeError('invalid type: ' + repr(annotation))
            return x

        return {
            bytes: lambda text: bytes(text, 'ascii')
        }.get(annotation, ensure_callable(annotation))

    def _construct_arg(self,
                       formal_param: inspect.Parameter,
                       value: str) -> Any:
            ctor = self.get_constructor(formal_param.annotation)
            try:
                return ctor(value)
            except ValueError as e:
                raise Cmd.CancelCmd(e)

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
        if len(free) > len(formal):
            raise Cmd.CancelCmd('too many free arguments: expected at most %d'
                                % (len(formal),))

        result = copy.deepcopy(actual)
        for name, value in zip(formal, free):
            if name in result:
                raise Cmd.CancelCmd('cannot assign free argument to %s: '
                                    'argument already present' % (name,))

            result[name] = self._construct_arg(formal[name], value)

        return result

    @staticmethod
    def _fill_default_args(formal: Mapping[str, inspect.Parameter],
                           actual: Mapping[str, str]):
        result = copy.deepcopy(actual)
        for name, param in formal.items():
            if (name not in result
                    and param.default is not inspect.Parameter.empty):
                result[name] = param.default

        return result

    def complete_impl(self, text, line, possibilities):
        words = line.strip().split()
        if words and '=' in words[-1] and line[-1] not in string.whitespace:
            try:
                key, val = words[-1].split('=', maxsplit=1)
                if len(possibilities[key]) > 0:
                    return match_string(val, possibilities[key], quiet=True)
            except ValueError:
                print('ValueError')

        matches = match_string(text, possibilities, quiet=True)
        return [x + '=' for x in matches]

    def completedefault(self, text, line, begidx, endidx):
        if re.match(r'^[^=]+=', text):
            return

        command = shlex.split(line)[0]
        handler = self._get_cmd_handler(command, quiet=True)

        arg_spec = inspect.getargspec(handler)
        return self.complete_impl(text, line, arg_spec.args[1:])

    def do_help(self,
                topic: str=''):
        all_handlers = self._get_all_commands()

        try:
            handler = self._choose_cmd_handler(all_handlers, topic)

            arg_spec = inspect.getargspec(handler)
            defaults = arg_spec.defaults or []
            args_with_defaults = list(zip(arg_spec.args[1:], # skip 'self'
                                          (default for _, default in defaults)))

            print('usage: %s %s'
                  % (topic.__name__,
                     ' '.join('%s=%s' % (arg, repr(default))
                              if default is not Cmd.Required else str(arg)
                              for arg, default in args_with_defaults)))
        except Cmd.CancelCmd:
            print('no such command: %s' % (topic,))
            print('available commands: %s' % (' '.join(sorted(all_handlers)),))

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

    def _get_all_commands(self) -> Mapping[str, Callable]:
        import types

        def unbind(f):
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
        matches = match_string(short_cmd, cmds, quiet)

        if not matches:
            raise Cmd.CancelCmd('no such command: %s' % (short_cmd,))
        elif len(matches) > 1:
            raise Cmd.CancelCmd('ambigious command: %s (possible: %s)'
                                % (short_cmd, ' '.join(matches)))
        else:
            return cmds[matches[0]]

    def _get_handler_params(_, handler) -> OrderedMapping[str, inspect.Parameter]:
        params = inspect.signature(handler).parameters
        params = collections.OrderedDict(list(params.items())[1:]) # drop 'self'
        return params

    def onecmd(self, cmdline):
        return self.default(cmdline)

    def _execute_cmd(self,
                     cmd: CommandInvocation):
        all_commands = self._get_all_commands()
        handler = self._choose_cmd_handler(all_commands, cmd.command)
        formal_params = self._get_handler_params(handler)
        typed_args = self._construct_args(formal_params,
                                          cmd.named_args, cmd.free_args)

        return handler(self, **typed_args)

    def default(self, cmdline):
        if not cmdline:
            return self.emptyline()

        try:
            return self._execute_cmd(CommandInvocation.from_cmdline(cmdline))
        except Cmd.CancelCmd as e:
            print(e)

    def cmdloop(self):
        try:
            cmd.Cmd.cmdloop(self)
        except KeyboardInterrupt:
            pass
