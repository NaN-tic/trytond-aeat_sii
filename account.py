# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from .aeat import (BOOK_KEY, OPERATION_KEY, SEND_SPECIAL_REGIME_KEY,
    RECEIVE_SPECIAL_REGIME_KEY, IVA_SUBJECTED, EXEMPTION_CAUSE)


__all__ = ['TemplateTax', 'Tax']

class TemplateTax(metaclass=PoolMeta):
    __name__ = 'account.tax.template'

    sii_book_key = fields.Selection(BOOK_KEY, 'Book Key')
    sii_operation_key = fields.Selection(OPERATION_KEY, 'SII Operation Key')
    sii_issued_key = fields.Selection(SEND_SPECIAL_REGIME_KEY, 'Issued Key')
    sii_received_key = fields.Selection(RECEIVE_SPECIAL_REGIME_KEY,
        'Received Key')
    sii_subjected_key = fields.Selection(IVA_SUBJECTED, 'Subjected Key')
    sii_exemption_cause = fields.Selection(EXEMPTION_CAUSE, 'Exemption Cause')
    tax_used = fields.Boolean('Used in Tax')
    invoice_used = fields.Boolean('Used in invoice Total')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        exist_sii_excemption_key = table.column_exist('sii_excemption_key')
        exist_sii_intracomunity_key = table.column_exist('sii_intracomunity_key')

        super(TemplateTax, cls).__register__(module_name)

        if exist_sii_excemption_key:
            # Don't use UPDATE FROM because SQLite nor MySQL support it.
            cursor.execute(*sql_table.update([sql_table.sii_exemption_cause],
                    [sql_table.sii_excemption_key])),
            table.drop_column('sii_excemption_key')

        if exist_sii_intracomunity_key:
            table.drop_column('sii_intracomunity_key')

    def _get_tax_value(self, tax=None):
        res = super(TemplateTax, self)._get_tax_value(tax)
        for field in ('sii_book_key', 'sii_operation_key', 'sii_issued_key',
                'sii_subjected_key', 'sii_exemption_cause', 'sii_received_key',
                'tax_used', 'invoice_used'):

            if not tax or getattr(tax, field) != getattr(self, field):
                res[field] = getattr(self, field)

        return res


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'

    sii_book_key = fields.Selection(BOOK_KEY, 'Book Key')
    sii_operation_key = fields.Selection(OPERATION_KEY, 'SII Operation Key')
    sii_issued_key = fields.Selection(SEND_SPECIAL_REGIME_KEY, 'Issued Key')
    sii_received_key = fields.Selection(RECEIVE_SPECIAL_REGIME_KEY,
        'Received Key')
    sii_subjected_key = fields.Selection(IVA_SUBJECTED, 'Subjected Key')
    sii_exemption_cause = fields.Selection(EXEMPTION_CAUSE, 'Exemption Cause')
    tax_used = fields.Boolean('Used in Tax')
    invoice_used = fields.Boolean('Used in invoice Total')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        exist_sii_excemption_key = table.column_exist('sii_excemption_key')
        exist_sii_intracomunity_key = table.column_exist('sii_intracomunity_key')

        super(Tax, cls).__register__(module_name)

        if exist_sii_excemption_key:
            # Don't use UPDATE FROM because SQLite nor MySQL support it.
            cursor.execute(*sql_table.update([sql_table.sii_exemption_cause],
                    [sql_table.sii_excemption_key])),
            table.drop_column('sii_excemption_key')

        if exist_sii_intracomunity_key:
            table.drop_column('sii_intracomunity_key')
