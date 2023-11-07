"""Test module for utils"""

from mcr_analyzer import utils


class TestEnsureList:
    def test___list(self):
        inp = [0, 1, 2]
        assert isinstance(utils.ensure_list(inp), list)

    def test___tuple(self):
        inp = (0, 1, 2)
        assert isinstance(utils.ensure_list(inp), tuple)

    def test___none(self):
        assert utils.ensure_list(None) == []

    def test___str(self):
        assert utils.ensure_list("abc") == [
            "abc",
        ]


class TestRemoveDuplicates:
    def test___identity(self):
        inp = [0, 1, 2]
        assert utils.remove_duplicates(inp) == inp

    def test___empty(self):
        assert utils.remove_duplicates([]) == []

    def test___single_element(self):
        assert utils.remove_duplicates([1]) == [1]

    def test___remove_consecutive(self):
        inp = [0, 1, 1, 2]
        out = [0, 1, 2]
        assert utils.remove_duplicates(inp) == out

    def test___remove_gap(self):
        inp = [0, 1, 2, 1]
        out = [0, 1, 2]
        assert utils.remove_duplicates(inp) == out

    def test___remove_all_but_one(self):
        inp = [0, 0]
        out = [0]
        assert utils.remove_duplicates(inp) == out


class TestSimplifyList:
    def test___single_string(self):
        inp = ["test"]
        out = "test"
        assert utils.simplify_list(inp) == out

    def test___multi_string(self):
        inp = ["one", "two"]
        out = ["one", "two"]
        assert utils.simplify_list(inp) == out

    def test___empty_list(self):
        inp = []
        out = []
        assert utils.simplify_list(inp) == out
