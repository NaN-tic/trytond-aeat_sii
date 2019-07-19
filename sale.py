# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from .invoice import _SII_INVOICE_KEYS

__all__ = ['Sale']


class Sale:
    'Sale'
    __name__ = 'sale.sale'
    __metaclass__ = PoolMeta

    def create_invoice(self, invoice_type):
        invoice = super(Sale, self).create_invoice(invoice_type)
        if not invoice:
            return

        if invoice_type in ('in_credit_note', 'out_credit_note'):
            invoice.sii_operation_key = 'R1'
        else:
            invoice.sii_operation_key = 'F1'

        tax = invoice.taxes and invoice.taxes[0]
        if not tax:
            return invoice

        for field in _SII_INVOICE_KEYS:
            setattr(invoice, field, getattr(tax.tax, field))
        invoice.save()

        return invoice
