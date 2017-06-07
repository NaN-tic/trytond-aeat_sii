# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from . import aeat

__all__ = ['Party']


class Party:
    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    # TODO: v4 change to party.identifier module
    identifier_type = fields.Selection([('', '')] + aeat.PARTY_IDENTIFIER_TYPE,
        'Identifier Type', )
    sii_vat_code = fields.Function(fields.Char('VAT', size=9),
        'get_sii_vat_data')
    sii_vat_country = fields.Function(fields.Char('VAT', size=2),
        'get_sii_vat_data')

    def get_sii_vat_data(self, name=None):
        if self.vat_code:
            if name == 'sii_vat_code':
                return self.vat_code[-9:]
            elif name == 'sii_vat_country':
                return self.vat_code[:2]
