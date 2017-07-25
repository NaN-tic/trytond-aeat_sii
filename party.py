# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from . import aeat

__all__ = ['Party']


class Party:
    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    sii_identifier_type = fields.Selection(aeat.PARTY_IDENTIFIER_TYPE,
        'SII Identifier Type')
    sii_vat_code = fields.Function(fields.Char('SII VAT Code', size=9),
        'get_sii_vat_data')
    sii_vat_country = fields.Function(fields.Char('SII VAT Country', size=2),
        'get_sii_vat_data')

    def get_sii_vat_data(self, name=None):
        if self.vat_code:
            if name == 'sii_vat_code':
                return (self.vat_code[-9:]
                    if self.type == 'eu_vat' else self.vat_code)
            elif name == 'sii_vat_country':
                return (self.vat_code[:2]
                    if self.type == 'eu_vat' else None)
