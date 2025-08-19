# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from . import aeat
from trytond.modules.party import Party as TAX_IDENTIFIER_TYPES

__all__ = ['Party', 'PartyIdentifier']


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    sii_identifier_type = fields.Selection(aeat.PARTY_IDENTIFIER_TYPE,
        'SII Identifier Type', sort=False)
    sii_vat_code = fields.Function(fields.Char('SII VAT Code', size=9),
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

    def default_sii_identifier_type():
        return 'SI'


class PartyIdentifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'

    @classmethod
    def set_sii_identifier_type(cls, identifiers):
        pool = Pool()
        Party = pool.get('party.party')

        to_write = []
        valid_identifier_by_party = {}
        for identifier in identifiers:
            if identifier.type in TAX_IDENTIFIER_TYPES:
                valid_identifier_by_party.setdefault(
                    identifier.party, []).append(identifier)

        for party, identifiers in valid_identifier_by_party.items():
            for identifier in identifiers:
                sii_identifier_type = None
                if ((identifier.type == 'eu_vat' and identifier.code[:2] == 'ES')
                        or identifier.type in ('es_cif', 'es_dni', 'es_nie',
                            'es_nif')):
                    sii_identifier_type = None
                elif identifier.type == 'eu_vat':
                    sii_identifier_type = '02'
                if sii_identifier_type:
                    break
            else:
                sii_identifier_type = '06'
            to_write.extend(([party], {
                'sii_identifier_type': sii_identifier_type}))

        if to_write:
            Party.write(*to_write)

    @classmethod
    def create(cls, vlist):
        identifiers = super(PartyIdentifier, cls).create(vlist)
        cls.set_sii_identifier_type(identifiers)
        return identifiers

    @classmethod
    def write(cls, *args):
        super(PartyIdentifier, cls).write(*args)

        def get_identifiers(identifiers):
            return list(set(identifiers))

        actions = iter(args)
        for identifiers, values in zip(actions, actions):
            cls.set_sii_identifier_type(get_identifiers(identifiers))

    @classmethod
    def delete(cls, identifiers):
        pool = Pool()
        Party = pool.get('party.party')

        parties = [i.party for i in identifiers]
        super().delete(identifiers)
        to_write = []
        for party in parties:
            if not party.tax_identifier:
                to_write.extend(([party], {
                    'sii_identifier_type': 'SI'}))
            else:
                cls.set_sii_identifier_type(party.identifiers)

        if to_write:
            Party.write(*to_write)
