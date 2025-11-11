# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta


class Document(metaclass=PoolMeta):
    __name__ = 'papyrus.document'

    def guess_invoice11(self):
        Invoice  = Pool().get('account.invoice')

        invoice = super().guess_invoice()
        Invoice.reset_sii_keys([invoice])
        return invoice

