# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.pool import PoolMeta
from .invoice import _SII_INVOICE_KEYS

__all__ = ['Sale']

ZERO = Decimal(0)


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def create_invoice(self):
        invoice = super(Sale, self).create_invoice()
        if not invoice:
            return

        # create_invoice() from sale not add untaxed_amount and taxes fields
        # call on_change_lines to add untaxed_amount and taxes
        invoice.on_change_lines()

        if invoice.untaxed_amount < ZERO:
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
