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
        vat_code = self.vat_code
        if vat_code:
            type = None
            for identifier in self.identifiers:
                if identifier.code == vat_code:
                    type = identifier.type
                    break
            if name == 'sii_vat_code':
                return vat_code[2:] if type == 'eu_vat' else vat_code
            elif name == 'sii_vat_country':
                return vat_code[:2] if type == 'eu_vat' else None
