import unittest
import inspect

from typing import Callable, Mapping

import test_utils

from powercmd.cmd import Cmd

class TestableCmd(Cmd):
    def _get_handler_params(cmd: Cmd,
                            handler: Callable) -> Mapping[str, inspect.Parameter]:
        unwrapped_handler = handler
        if isinstance(handler, test_utils.CallWrapper):
            unwrapped_handler = handler.fn

        return Cmd._get_handler_params(unwrapped_handler)

class TestCmd(unittest.TestCase):
    def test_get_constructor__callable(self):
        self.assertEqual(int, Cmd().get_constructor(int))

    def test_get_constructor__not_callable(self):
        with self.assertRaises(TypeError):
            Cmd().get_constructor(42)

    def test_get_all_commands(self):
        class TestImpl(Cmd):
            def do_test(_self):
                pass

        expected_commands = {
            'exit': Cmd.do_exit,
            'EOF': Cmd.do_EOF,
            'get_error': Cmd.do_get_error,
            'help': Cmd.do_help,
            'test': TestImpl.do_test
        }
        self.assertEqual(expected_commands, TestImpl()._get_all_commands())

    def test_construct_string(self):
        class TestImpl(TestableCmd):
            @test_utils.mock
            def do_test(_self, str_var: str):
                pass

        cmd = TestImpl()
        with cmd.do_test.expect_call(str_var='str'):
            cmd.default('test str')

    def test_construct_builtin(self):
        class TestImpl(TestableCmd):
            @test_utils.mock
            def do_test(_self, int_var: int):
                pass

        cmd = TestImpl()
        with cmd.do_test.expect_call(int_var=42):
            cmd.default('test 42')

    def test_construct_class(self):
        class ClassConstructor(str):
            pass

        class TestImpl(TestableCmd):
            @test_utils.mock
            def do_test(_self,
                        cls_var: ClassConstructor):
                pass

        cmd = TestImpl()
        with cmd.do_test.expect_call(cls_var=ClassConstructor('cls')):
            cmd.default('test cls')

    def test_construct_fn(self):
        def fn_constructor(string):
            return 'fn'

        class TestImpl(TestableCmd):
            @test_utils.mock
            def do_test(_self,
                        fn_var: fn_constructor):
                pass

        cmd = TestImpl()
        with cmd.do_test.expect_call(fn_var=fn_constructor('fn')):
            cmd.default('test fn')

    def test_construct_free(self):
        class TestImpl(TestableCmd):
            @test_utils.mock
            def do_test(_self,
                        first: str,
                        second: int):
                pass

        cmd = TestImpl()
        with cmd.do_test.expect_call(first='first',
                                     second=2):
            cmd.default('test first 2')

    def test_construct_named(self):
        class TestImpl(TestableCmd):
            @test_utils.mock
            def do_test(_self,
                        first: str,
                        second: int):
                pass

        cmd = TestImpl()
        with cmd.do_test.expect_call(first='first',
                                     second=2):
            cmd.default('test first=first second=2')
        with cmd.do_test.expect_call(first='first',
                                     second=2):
            cmd.default('test second=2 first=first')

    def test_construct_mixed_free_named(self):
        class TestImpl(TestableCmd):
            @test_utils.mock
            def do_test(_self,
                        first: str,
                        second: int):
                pass

        cmd = TestImpl()
        with cmd.do_test.expect_call(first='first',
                                     second=2):
            cmd.default('test first second=2')
        with cmd.do_test.expect_no_calls():
            cmd.default('test first=first 2')

    def test_completedefault(self):
        class TestImpl(TestableCmd):
            @test_utils.mock
            def do_test(_self,
                        arg_first: str,
                        arg_second: int,
                        third: str):
                pass

        def complete_args(cmdline):
            space_at = cmdline.rfind(' ')
            return [cmdline.split()[-1], cmdline, space_at, len(cmdline)]

        cmd = TestImpl()

        self.assertEqual(['arg_first=', 'arg_second=', 'third='],
                         cmd.completedefault(*complete_args('test ')))
        self.assertEqual(['arg_first=', 'arg_second='],
                         cmd.completedefault(*complete_args('test arg')))
        self.assertEqual(['arg_first='],
                         cmd.completedefault(*complete_args('test arg_f')))

    def test_completedefault_custom_completer(self):
        class TestType(object):
            @test_utils.static_mock
            @staticmethod
            def powercmd_complete(text):
                print(text)
                return ['complete'] if 'complete'.startswith(text) else []

            def __init__(self, s):
                self.s = s

        class TestImpl(TestableCmd):
            @test_utils.mock
            def do_test(_self,
                        arg: TestType):
                pass

        def complete_args(cmdline):
            space_at = cmdline.rfind(' ')
            return [cmdline.split()[-1], cmdline, space_at, len(cmdline)]

        cmd = TestImpl()

        with TestType.powercmd_complete.expect_no_calls() as _, \
             cmd.do_test.expect_no_calls() as _:
            self.assertEqual(['arg='],
                             cmd.completedefault(*complete_args('test arg')))

        with TestType.powercmd_complete.expect_call('c') as _, \
             cmd.do_test.expect_no_calls() as _:
            self.assertEqual(['arg=complete'],
                             cmd.completedefault(*complete_args('test arg=c')))
