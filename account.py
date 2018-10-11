# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from .aeat import (BOOK_KEY, SEND_SPECIAL_REGIME_KEY,
    RECEIVE_SPECIAL_REGIME_KEY, IVA_SUBJECTED, EXCEMPTION_CAUSE,
    INTRACOMUNITARY_TYPE)


__all__ = ['TemplateTax', 'Tax']


class TemplateTax(metaclass=PoolMeta):
    __name__ = 'account.tax.template'

    sii_book_key = fields.Selection(BOOK_KEY, 'Book Key')
    sii_issued_key = fields.Selection(SEND_SPECIAL_REGIME_KEY, 'Issued Key')
    sii_received_key = fields.Selection(RECEIVE_SPECIAL_REGIME_KEY,
        'Received Key')
    sii_intracomunity_key = fields.Selection(INTRACOMUNITARY_TYPE,
        'Intracommunity Key')
    sii_subjected_key = fields.Selection(IVA_SUBJECTED, 'Subjected Key')
    sii_excemption_key = fields.Selection(EXCEMPTION_CAUSE, 'Excemption Key')
    tax_used = fields.Boolean('Used in Tax')
    invoice_used = fields.Boolean('Used in invoice Total')

    def _get_tax_value(self, tax=None):
        res = super(TemplateTax, self)._get_tax_value(tax)
        for field in ('sii_book_key', 'sii_issued_key', 'sii_subjected_key',
                'sii_excemption_key', 'sii_received_key',
                'sii_intracomunity_key', 'tax_used', 'invoice_used'):

            if not tax or getattr(tax, field) != getattr(self, field):
                res[field] = getattr(self, field)

        return res


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'

    sii_book_key = fields.Selection(BOOK_KEY, 'Book Key')
    sii_issued_key = fields.Selection(SEND_SPECIAL_REGIME_KEY, 'Issued Key')
    sii_received_key = fields.Selection(RECEIVE_SPECIAL_REGIME_KEY,
        'Received Key')
    sii_intracomunity_key = fields.Selection(INTRACOMUNITARY_TYPE,
        'Intracommunity Key')
    sii_subjected_key = fields.Selection(IVA_SUBJECTED, 'Subjected Key')
    sii_excemption_key = fields.Selection(EXCEMPTION_CAUSE, 'Excemption Key')
    tax_used = fields.Boolean('Used in Tax')
    invoice_used = fields.Boolean('Used in invoice Total')
