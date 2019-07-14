# -*- coding: utf-8 -*-
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import doctest_teardown
from trytond.tests.test_tryton import doctest_checker
from trytond.modules.aeat_sii.tools import unaccent


class AeatSIITestCase(ModuleTestCase):
    'Test AEAT SII module'
    module = 'aeat_sii'

    def test_unaccent(self):
        for value, result in [
                ('aeiou', 'aeiou'),
                ('áéíóú', 'aeiou'),
                ('__aéiou__', 'aeiou'),
                ('__aé@ou__', 'ae_ou'),
                (u'aeiou', 'aeiou'),
                (u'áéíóú', 'aeiou'),
                (b'aeiou', 'aeiou'),
                ]:
            self.assertEqual(unaccent(value), result)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AeatSIITestCase))
    suite.addTests(doctest.DocFileSuite('scenario_aeat_sii.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            checker=doctest_checker,
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
