# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

"""Test module for utils"""

import mcr_analyser.utils as utils


class TestEnsureList:
    def test_list(self):
        input = [0, 1, 2]
        assert isinstance(utils.ensure_list(input), list)

    def test_tuple(self):
        input = (0, 1, 2)
        assert isinstance(utils.ensure_list(input), tuple)

    def test_none(self):
        assert utils.ensure_list(None) == []

    def test_str(self):
        assert utils.ensure_list("abc") == [
            "abc",
        ]


class TestRemoveDuplicates:
    def test_identity(self):
        input = [0, 1, 2]
        assert utils.remove_duplicates(input) == input

    def test_empty(self):
        assert utils.remove_duplicates([]) == []

    def test_single_element(self):
        assert utils.remove_duplicates([1]) == [1]

    def test_remove_consecutive(self):
        input = [0, 1, 1, 2]
        output = [0, 1, 2]
        assert utils.remove_duplicates(input) == output

    def test_remove_gap(self):
        input = [0, 1, 2, 1]
        output = [0, 1, 2]
        assert utils.remove_duplicates(input) == output

    def test_remove_all_but_one(self):
        input = [0, 0]
        output = [0]
        assert utils.remove_duplicates(input) == output


class TestSimplyList:
    def test_single_string(self):
        input = ["test"]
        output = "test"
        assert utils.simplify_list(input) == output

    def test_multi_string(self):
        input = ["one", "two"]
        output = ["one", "two"]
        assert utils.simplify_list(input) == output
