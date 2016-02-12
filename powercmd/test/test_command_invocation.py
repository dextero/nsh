import unittest

from powercmd.command_invocation import CommandInvocation

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

