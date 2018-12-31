# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from . import aeat

__all__ = ['Party']


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    sii_identifier_type = fields.Selection(aeat.PARTY_IDENTIFIER_TYPE,
        'SII Identifier Type')
    sii_vat_code = fields.Function(fields.Char('SII VAT Code', size=9),
        'get_sii_vat_data')
    sii_vat_country = fields.Function(fields.Char('SII VAT Country', size=2),
        'get_sii_vat_data')

    def get_sii_vat_data(self, name=None):
        identifier = self.tax_identifier or (
            self.identifiers and self.identifiers[0])
        if identifier:
            if name == 'sii_vat_code':
                if (identifier.type == 'eu_vat' and
                        not identifier.code.startswith('ES') and
                        self.sii_identifier_type == '02'):
                    return identifier.code
                return identifier.code[2:]
            elif name == 'sii_vat_country':
                return identifier.code[:2]
