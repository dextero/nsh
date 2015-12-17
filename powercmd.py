#!/usr/bin/env python3.5

import cmd
import copy
import inspect
import re
import shlex
import os
import string

from typing import Callable, List, Sequence, Mapping, Tuple

class TextMatchStrategy(object):
    """
    Represents a method of checking if given text matches a pattern.
    """
    def __init__(self,
                 name: str,
                 matcher: Callable[[str, str], bool]):
        self.name = name
        self.matcher = matcher

    def __call__(self,
                 text: str,
                 pattern: str) -> bool:
        return self.matcher(text, pattern)

    @staticmethod
    def _prefixes_of(text: str) -> Sequence[str]:
        """
        Returns all prefixes if given TEXT including itself, longest first.
        """
        for i in range(len(text)):
            yield text[i:]

    @staticmethod
    def _matches_words(text: str,
                       words: Sequence[str]) -> bool:
        """
        Returns true if given TEXT can be assembled from non-empty prefixes of
        WORDS in order.

        Examples:
            _matches_words("po", ["prefixes", "of"]) => True
            _matches_words("gval", ["get", "value"]) => True
            _matches_words("gv", ["get", "total", "value", "of", "xs"]) => False
            _matches_words("st", ["set", "foo"]) => False
        """
        if not text:
            return True

        for word in words:
            common_prefix = os.path.commonprefix([text, word])
            if not common_prefix:
                return False
            elif common_prefix == text:
                return True

            for prefix in TextMatchStrategy._prefixes_of(common_prefix):
                if TextMatchStrategy._matches_words(text[len(prefix):],
                                                    words[1:]):
                    return True
        return False

    @staticmethod
    def snake_case_matches(short: str,
                           full: str) -> bool:
        """
        Checks if SHORT is an abbreviation of FULL snake-case text.

        Examples:
            snake_case_matches("po", "prefixes_of") => True
            snake_case_matches("gval", "get_value") => True
            snake_case_matches("gv", "get_total_value_of_foo") => False
            snake_case_matches("st", "set_foo") => False
        """
        return TextMatchStrategy._matches_words(short, full.split('_'))

    @staticmethod
    def fuzzy_matches(short: str,
                      full: str) -> bool:
        """
        Checks if FULL contains all elements of SHORT in the same order. That
        does not mean that SHORT == FULL - FULL can contain other elements not
        present in SHORT.
        """
        short_at = 0
        for char in full:
            if char == short[short_at]:
                short_at += 1
                if short_at == len(short):
                    return True
        return False

TextMatchStrategy.Exact = \
        TextMatchStrategy('exact', lambda a, b: a == b)
TextMatchStrategy.Prefix = \
        TextMatchStrategy('prefix', lambda short, full: full.startswith(short))
TextMatchStrategy.SnakeCase = \
        TextMatchStrategy('snake case', TextMatchStrategy.snake_case_matches)
TextMatchStrategy.Fuzzy = \
        TextMatchStrategy('fuzzy', TextMatchStrategy.fuzzy_matches)

def _match_string(text: str,
                  possible: Sequence[str],
                  match_strategies: Sequence[Tuple[str, Callable[[str, str], bool]]],
                  quiet: bool) -> List[str]:
    """
    Attempts to match TEXT to one of POSSIBLE, using multiple MATCH_STRATEGIES.
    Returns after any of MATCH_STRATEGIES finds some matches, i.e. the return
    value will always contain elements matched using the same strategy.

    Prints the name of successful strategy unless QUIET is set to True.

    Returns the list of matches sorted in alphabetical order.
    """
    for name, match in match_strategies:
        matches = sorted([e for e in possible if match(text, e)])
        if matches:
            if not quiet:
                print('* %s: %s' % (name, ' '.join(matches)))
            return matches

    return []

def simple_match_string(text, possible):
    match_strategies = [
        TextMatchStrategy.Exact,
        TextMatchStrategy.Prefix
    ]
    return _match_string(text, possible, match_strategies, quiet=False)

def match_string(text, possible, quiet=False):
    match_strategies = [
        TextMatchStrategy.Exact,
        TextMatchStrategy.Prefix,
        TextMatchStrategy.SnakeCase,
        TextMatchStrategy.Fuzzy
    ]
    return _match_string(text, possible, match_strategies, quiet=quiet)

class CommandInvocation(object):
    def __init__(self,
                 command: str,
                 named_args: Mapping[str, str]=None,
                 free_args: Sequence[str]=None):
        self.command = command
        self.named_args = named_args or {}
        self.free_args = free_args or []

    def __eq__(self, other):
        return ((self.command, self.named_args, self.free_args)
                == (other.command, other.named_args, other.free_args))

    def __str__(self):
        return ('command = %s\nnamed_args (%d):\n%s\nfree_args (%d):\n%s'
                % (self.command,
                   len(self.named_args),
                   '\n'.join('  %s=%s' % kv for kv in self.named_args),
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
        named_args = {}
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

class Cmd(cmd.Cmd):
    CMD_PREFIX = 'do_'

    class CancelCmd(Exception):
        pass

    def do_exit(self, _=(None, None)):
        print('exiting')
        return True

    def do_EOF(self, _=(None, None)):
        print('')
        return self.do_exit(_)

    @staticmethod
    def _parse_args(formal: Mapping[str, inspect.Parameter],
                    actual: Mapping[str, str]):
        """
        Parses a list of actual call parameters by calling an appropriate
        constructor for each of them.
        """
        parsed_args = {}
        free = []

        for name, value in actual.items():
            if name not in formal:
                print('unrecognized argument: %s' % (name,))
                free.append('%s=%s' % (name, value))
            else:
                ctor = formal.annotation
                if not ctor or ctor.__call__ is None:
                    print('constructor for parameter %s missing or not '
                          'callable, using str')
                    ctor = str

                try:
                    if ctor is bytes:
                        ctor = lambda v: bytes(v, 'ascii')
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

            ctor, _ = formal[name]
            try:
                result[name] = ctor(value)
            except ValueError as e:
                raise Cmd.CancelCmd(e)

        return result

    @staticmethod
    def _fill_default_args(formal,
                           actual):
        result = copy.deepcopy(actual)
        for name, (_, default) in formal.items():
            if (name not in result
                    and default is not Cmd.Required):
                result[name] = default

        return result

    @staticmethod
    def _validate_args(formal,
                       actual):
        for name, (_, default) in formal.items():
            if (name not in actual
                    and default is Cmd.Required):
                raise Cmd.CancelCmd('missing required argument: %s' % (name,))

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
        command, handler = self._expand_cmd(command, quiet=True)

        arg_spec = inspect.getargspec(handler)
        return self.complete_impl(text, line, arg_spec.args[1:])

    def do_help(self, topic=(str, '')):
        try:
            topic, handler = self._expand_cmd(topic)

            arg_spec = inspect.getargspec(handler)
            defaults = arg_spec.defaults or []
            args_with_defaults = list(zip(arg_spec.args[1:], # skip 'self'
                                          (default for _, default in defaults)))

            print('usage: %s %s'
                  % (topic,
                     ' '.join('%s=%s' % (arg, repr(default))
                              if default is not Cmd.Required else str(arg)
                              for arg, default in args_with_defaults)))
        except Cmd.CancelCmd:
            pass # unknown command, use default do_help handler

        return cmd.Cmd.do_help(self, topic)

    def _get_all_cmds(self):
        members = inspect.getmembers(self)
        return dict((k[len(Cmd.CMD_PREFIX):], v) for k, v in members
                    if (inspect.ismethod(v)
                        and k.startswith(Cmd.CMD_PREFIX)))

    def _expand_cmd(self, short_cmd, quiet=False):
        cmds = self._get_all_cmds()
        matches = match_string(short_cmd, cmds, quiet)

        if not matches:
            raise Cmd.CancelCmd('no such command: %s' % (short_cmd,))
        elif len(matches) > 1:
            raise Cmd.CancelCmd('ambigious command: %s (possible: %s)'
                                % (short_cmd, ' '.join(matches)))
        else:
            return matches[0], cmds[matches[0]]

    def onecmd(self, cmdline):
        return self.default(cmdline)

    @staticmethod
    def _get_handler_params(handler):
        sig = inspect.signature(handler)
        return sig.parameters[1:] # skip 'self'

    def default(self, cmdline):
        if not cmdline:
            return self.emptyline()

        cmd, args, free = Cmd._split_cmdline(cmdline)

        try:
            name, handler = self._expand_cmd(cmd)
            formal_params = Cmd._get_handler_params(handler)

            parsed_args, extra_free = Cmd._parse_args(formal_params, args)
            parsed_args = Cmd._assign_free_args(formal_params, parsed_args,
                                                free + extra_free)
            parsed_args = Cmd._fill_default_args(formal_params, parsed_args)

            Cmd._validate_args(formal_params, parsed_args)
            return handler(**parsed_args)
        except Cmd.CancelCmd as e:
            print(e)

    def cmdloop(self):
        try:
            cmd.Cmd.cmdloop(self)
        except KeyboardInterrupt:
            pass

import unittest

class TestCommandInvocation(unittest.TestCase):
    def test_parse(self):
        assertEqual = self.assertEqual

        assertEqual(CommandInvocation(command=''),
                    CommandInvocation.from_cmdline(''))
        assertEqual(CommandInvocation(command='foo'),
                    CommandInvocation.from_cmdline('foo'))

        assertEqual(CommandInvocation(command='foo', free_args=['bar']),
                    CommandInvocation.from_cmdline('foo bar'))

        assertEqual(CommandInvocation(command='foo', free_args=['bar']),
                    CommandInvocation.from_cmdline('foo\tbar'))
        assertEqual(CommandInvocation(command='foo', free_args=['bar']),
                    CommandInvocation.from_cmdline('foo \tbar'))

        assertEqual(CommandInvocation(command='foo', free_args=['bar \tbaz']),
                    CommandInvocation.from_cmdline('foo "bar \tbaz"'))
        assertEqual(CommandInvocation(command='foo', free_args=['bar \tbaz']),
                    CommandInvocation.from_cmdline('foo \'bar \tbaz\''))

        assertEqual(CommandInvocation(command='foo', named_args={'bar': 'baz'}),
                    CommandInvocation.from_cmdline('foo bar=baz'))

