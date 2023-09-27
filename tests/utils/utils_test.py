"""Test module for utils"""

from mcr_analyzer import utils


class TestEnsureList:
    def test_list(self):
        inp = [0, 1, 2]
        assert isinstance(utils.ensure_list(inp), list)

    def test_tuple(self):
        inp = (0, 1, 2)
        assert isinstance(utils.ensure_list(inp), tuple)

    def test_none(self):
        assert utils.ensure_list(None) == []

    def test_str(self):
        assert utils.ensure_list("abc") == [
            "abc",
        ]


class TestRemoveDuplicates:
    def test_identity(self):
        inp = [0, 1, 2]
        assert utils.remove_duplicates(inp) == inp

    def test_empty(self):
        assert utils.remove_duplicates([]) == []

    def test_single_element(self):
        assert utils.remove_duplicates([1]) == [1]

    def test_remove_consecutive(self):
        inp = [0, 1, 1, 2]
        out = [0, 1, 2]
        assert utils.remove_duplicates(inp) == out

    def test_remove_gap(self):
        inp = [0, 1, 2, 1]
        out = [0, 1, 2]
        assert utils.remove_duplicates(inp) == out

    def test_remove_all_but_one(self):
        inp = [0, 0]
        out = [0]
        assert utils.remove_duplicates(inp) == out


class TestSimplifyList:
    def test_single_string(self):
        inp = ["test"]
        out = "test"
        assert utils.simplify_list(inp) == out

    def test_multi_string(self):
        inp = ["one", "two"]
        out = ["one", "two"]
        assert utils.simplify_list(inp) == out

    def test_empty_list(self):
        inp = []
        out = []
        assert utils.simplify_list(inp) == out
