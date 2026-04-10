import unittest

from pydantic import BaseModel

from common.state import Pos, json_to_pos, pos_to_json


class Foo(BaseModel):
    p: Pos


class TestStateSerialization(unittest.TestCase):
    def test_pos(self):
        """
        Pos is unique (needs a serializer and validator) so we write a test for it.
        """
        p: Pos = (10, 20)
        s = pos_to_json(p)
        self.assertEqual(s, "10:20")
        p2 = json_to_pos(s)
        self.assertEqual(p, p2)

        foo = Foo(p=p)
        s = foo.model_dump_json()
        self.assertEqual(s, '{"p":"10:20"}')
        self.assertEqual(Foo.model_validate_json(s), foo)
