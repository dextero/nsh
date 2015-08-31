#!/usr/bin/env python3

import cmd
import copy
import inspect
import re
import shlex

class Required(object): pass

class Cmd(cmd.Cmd):
    CMD_PREFIX = 'do_'

    class CancelCmd(Exception): pass

    def do_exit(self, _=(None, None)):
        print('exiting')
        return True

    def do_EOF(self, _=(None, None)):
        print('')
        return self.do_exit(_)

    @staticmethod
    def _split_cmdline(cmdline):
        words = shlex.split(cmdline)

        cmd = words[0]
        args = {}
        free = []

        for w in words[1:]:
            if re.match(r'^[a-zA-Z0-9_]+=', w):
                k, v = w.split('=', maxsplit=1)
                if k in args:
                    raise Cmd.CancelCmd('multiple values for key: %s' % (k,))
                else:
                    args[k] = v
            else:
                free.append(w)

        return (cmd, args, free)

    @staticmethod
    def _parse_args(formal,
                    actual):
        parsed_args = {}
        free = []

        for name, value in actual.items():
            if name not in formal:
                print('unrecognized argument: %s' % (name,))
                free.append('%s=%s' % (name, value))
            else:
                ctor, _ = formal[name]
                try:
                    parsed_args[name] = ctor(value)
                except ValueError as e:
                    raise Cmd.CancelCmd(e)

        return parsed_args, free

    @staticmethod
    def _assign_free_args(formal,
                          actual,
                          free):
        if len(free) > len(formal):
            raise Cmd.CancelCmd('too many free arguments: expected at most %d'
                                % (len(formal),))

        result = copy.deepcopy(actual)
        for name, value in zip(formal, free):
            if name in result:
                raise Cmd.CancelCmd('cannot assign free argument to %s: '
                                    'argument already present' % (name,))

            result[name] = value

        return result

    @staticmethod
    def _fill_default_args(formal,
                           actual):
        result = copy.deepcopy(actual)
        for name, (_, default) in formal.items():
            if (name not in result
                    and default is not Required):
                result[name] = default

        return result

    @staticmethod
    def _validate_args(formal,
                       actual):
        for name, (_, default) in formal.items():
            if (name not in actual
                    and default is Required):
                raise Cmd.CancelCmd('missing required argument: %s' % (name,))

    def completedefault(self, text, line, begidx, endidx):
        if re.match(r'^[^=]+=', text):
            return

        cmd = shlex.split(line)[0]
        cmd, handler = self._expand_cmd(cmd)

        arg_spec = inspect.getargspec(handler)
        matches = [e for e in arg_spec.args[1:] if e.startswith(text)]
        return [x + '=' for x in matches]

    def do_help(self, topic=(str, '')):
        try:
            topic, handler = self._expand_cmd(topic)

            arg_spec = inspect.getargspec(handler)
            defaults = arg_spec.defaults or []
            args_with_defaults = list(zip(arg_spec.args[1:], # skip 'self'
                                      (default for _, default in defaults)))

            print('usage: %s %s' % (
                      topic,
                      ' '.join('%s=%s' % (arg, repr(default)) if default is not Required
                                                              else str(arg)
                      for arg, default in args_with_defaults)))
        except Cmd.CancelCmd:
            pass # unknown command, use default do_help handler

        return cmd.Cmd.do_help(self, topic)

    def _get_all_cmds(self):
        return dict((k[len(Cmd.CMD_PREFIX):], v) for k, v in inspect.getmembers(self)
                    if (inspect.ismethod(v)
                        and k.startswith(Cmd.CMD_PREFIX)))
    def _expand_cmd(self, short_cmd):
        cmds = self._get_all_cmds()
        matches = sorted([e for e in cmds if e.startswith(short_cmd)])

        if not matches:
            raise Cmd.CancelCmd('no such command: %s' % (short_cmd,))
        elif cmd in matches:
            return cmd, cmds[cmd]
        elif len(matches) > 1:
            raise Cmd.CancelCmd('ambigious command: %s (possible: %s)'
                                % (cmdline, ' '.join(matches)))
        else:
            return matches[0], cmds[matches[0]]

    def onecmd(self, cmdline):
        return self.default(cmdline)

    def default(self, cmdline):
        cmd, args, free = Cmd._split_cmdline(cmdline)

        try:
            name, handler = self._expand_cmd(cmd)

            arg_spec = inspect.getargspec(handler)
            defaults = arg_spec.defaults or []
            formal = dict(zip(arg_spec.args[1:], # skip 'self'
                              defaults))

            parsed_args, extra_free = Cmd._parse_args(formal, args)
            parsed_args = Cmd._assign_free_args(formal, parsed_args,
                                                free + extra_free)
            parsed_args = Cmd._fill_default_args(formal, parsed_args)
            Cmd._validate_args(formal, parsed_args)
            return handler(**parsed_args)
        except Cmd.CancelCmd as e:
            print(e)

    def cmdloop(self):
        try:
            cmd.Cmd.cmdloop(self)
        except KeyboardInterrupt:
            pass
