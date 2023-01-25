# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from .invoice import _SII_INVOICE_KEYS

__all__ = ['Purchase']


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    def create_invoice(self):
        invoice = super(Purchase, self).create_invoice()

        if invoice:
            # create_invoice() from purchase not add taxes fields
            # call on_change_lines to add taxes
            invoice.on_change_lines()
            tax = invoice.taxes and invoice.taxes[0]
            if not tax:
                return invoice

            for field in _SII_INVOICE_KEYS:
                setattr(invoice, field, getattr(tax.tax, field))

        return invoice
