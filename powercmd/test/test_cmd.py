import unittest
import inspect

from typing import Callable, Mapping

import test_utils

from cmd import Cmd

class TestableCmd(Cmd):
    def _get_handler_params(cmd: Cmd,
                            handler: Callable) -> Mapping[str, inspect.Parameter]:
        unwrapped_handler = handler
        if isinstance(handler, test_utils.CallWrapper):
            unwrapped_handler = handler.fn

        return Cmd._get_handler_params(cmd, unwrapped_handler)

class TestCmd(unittest.TestCase):
    def test_get_cmd_handler(self):
        class TestImpl(TestableCmd):
            def do_test(_self):
                pass

        cmd = TestImpl()

        self.assertEqual(cmd.do_test, cmd._get_cmd_handler('test'))
        self.assertEqual(cmd.do_test, cmd._get_cmd_handler('t'))

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

