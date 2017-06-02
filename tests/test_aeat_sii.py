# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
# import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
# TODO: Remove if no sceneario needed.
# from trytond.tests.test_tryton import doctest_setup, doctest_teardown


class AeatSIITestCase(ModuleTestCase):
    'Test AEAT SII module'
    module = 'aeat_sii'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        AeatSIITestCase))
    # TODO: remove if no scenario needed.
    #suite.addTests(doctest.DocFileSuite('scenario_aeat_sii.rst',
    #        setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
    #        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
