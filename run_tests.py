#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import sys
import os

class TestTravis(unittest.TestCase):
    def test_travis(self):
        self.assertEqual(2, 2)

if __name__ == '__main__':
    unittest.main()
