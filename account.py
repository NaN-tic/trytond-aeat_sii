# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, And, Bool
from trytond.transaction import Transaction
from .aeat import (OPERATION_KEY, BOOK_KEY, SEND_SPECIAL_REGIME_KEY,
        RECEIVE_SPECIAL_REGIME_KEY, AEAT_INVOICE_STATE, IVA_SUBJECTED,
        EXCEMPTION_CAUSE, INTRACOMUNITARY_TYPE)


__all__ = ['TemplateTax', 'Tax']


class TemplateTax:
    __name__ = 'account.tax.template'
    __metaclass__ = PoolMeta

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
                'sii_intracomunity_key'):

            if not tax or getattr(tax, field) != getattr(self, field):
                res[field] = getattr(self, field)

        return res


class Tax:
    __name__ = 'account.tax'
    __metaclass__ = PoolMeta

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
