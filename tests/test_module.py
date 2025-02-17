
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.tests.test_tryton import ModuleTestCase
from trytond.modules.aeat_sii.tools import unaccent
from trytond.modules.company.tests import CompanyTestMixin


class AeatSiiTestCase(CompanyTestMixin, ModuleTestCase):
    'Test AeatSii module'
    module = 'aeat_sii'
    extras = ['account_invoice_intercompany', 'party_identifier', 'sale',
        'purchase', 'aeat_303']

    def test_unaccent(self):
        for value, result in [
                ('aeiou', b'aeiou'),
                ('áéíóú', b'aeiou'),
                ('__aéiou__', b'aeiou'),
                ('__aé@ou__', b'aeou'),
                ]:
            self.assertEqual(unaccent(value), result)


del ModuleTestCase
