# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.pool import PoolMeta

__all__ = ['Sale']
__metaclass__ = PoolMeta

ZERO = Decimal('0.0')


class Sale:
    'Sale'
    __name__ = 'sale.sale'

    def create_invoice(self):
        invoice = super(Sale, self).create_invoice()
        if invoice:
            if invoice.untaxed_amount < ZERO:
                invoice.sii_operation_key = 'R1'
            else:
                invoice.sii_operation_key = 'F1'

        return invoice
