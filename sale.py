# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = ['Sale']
__metaclass__ = PoolMeta


class Sale:
    'Sale'
    __name__ = 'sale.sale'

    def _get_invoice_sale(self, invoice_type):
        invoice = super(Sale, self)._get_invoice_sale(invoice_type)
        if invoice_type in ('in_credit_note', 'out_credit_note'):
            invoice.sii_operation_key = 'R1'
        else:
            invoice.sii_operation_key = 'F1'

        return invoice
