# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields, ModelSQL
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.modules.company.model import CompanyValueMixin
from .aeat import (BOOK_KEY, OPERATION_KEY, SEND_SPECIAL_REGIME_KEY,
    RECEIVE_SPECIAL_REGIME_KEY, IVA_SUBJECTED, EXEMPTION_CAUSE)


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    aeat_certificate_sii = fields.MultiValue(fields.Many2One('certificate',
        'AEAT Certificate SII'))
    aeat_pending_sii = fields.MultiValue(fields.Boolean('AEAT Pending SII',
        help='Automatically generate AEAT Pending SII reports by cron'))
    aeat_pending_sii_send = fields.MultiValue(fields.Boolean('AEAT Pending SII Send',
        states={
            'invisible': ~Eval('aeat_pending_sii', False),
        },
        help='Automatically send AEAT Pending SII reports by cron'))
    aeat_received_sii = fields.MultiValue(fields.Boolean('AEAT Received SII',
        help='Automatically generate AEAT Received SII reports by cron'))
    aeat_received_sii_send = fields.MultiValue(fields.Boolean('AEAT Received SII Send',
        states={
            'invisible': ~Eval('aeat_received_sii', False),
        },
        help='Automatically send AEAT Received SII reports by cron'))
    not_allow_out_invoices_aeat_sii_keys = fields.MultiValue(fields.Boolean(
        'Not allow post out invoices without AEAT SII Keys'))
    not_allow_in_invoices_aeat_sii_keys = fields.MultiValue(fields.Boolean(
        'Not allow post in invoices without AEAT SII Keys'))
    sii_default_offset_days = fields.MultiValue(fields.Integer('SII Default Offset Days',
        help='Default offset days in the invoices search for the SII Books'))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'aeat_certificate_sii', 'aeat_pending_sii',
                'aeat_pending_sii_send', 'aeat_received_sii',
                'aeat_received_sii_send',
                'not_allow_out_invoices_aeat_sii_keys',
                'not_allow_in_invoices_aeat_sii_keys',
                'sii_default_offset_days'}:
            return pool.get('account.configuration.default_sii')
        return super().multivalue_model(field)

    @classmethod
    def default_aeat_pending_sii(cls, **pattern):
        return False

    @classmethod
    def default_aeat_received_sii(cls, **pattern):
        return False

    @classmethod
    def default_aeat_pending_sii_send(cls, **pattern):
        return False

    @classmethod
    def default_aeat_received_sii_send(cls, **pattern):
        return False

    @classmethod
    def default_not_allow_out_invoices_aeat_sii_keys(cls, **pattern):
        return False

    @classmethod
    def default_not_allow_in_invoices_aeat_sii_keys(cls, **pattern):
        return False

    @classmethod
    def default_sii_default_offset_days(cls, **pattern):
        return 0


class ConfigurationDefaultSII(ModelSQL, CompanyValueMixin):
    "Account Configuration Default SII Values"
    __name__ = 'account.configuration.default_sii'

    aeat_certificate_sii = fields.Many2One('certificate',
        'AEAT Certificate SII')
    aeat_pending_sii = fields.Boolean('AEAT Pending SII',
        help='Automatically generate AEAT Pending SII reports by cron')
    aeat_pending_sii_send = fields.Boolean('AEAT Pending SII Send',
        states={
            'invisible': ~Eval('aeat_pending_sii', False),
        },
        help='Automatically send AEAT Pending SII reports by cron')
    aeat_received_sii = fields.Boolean('AEAT Received SII',
        help='Automatically generate AEAT Received SII reports by cron')
    aeat_received_sii_send = fields.Boolean('AEAT Received SII Send',
        states={
            'invisible': ~Eval('aeat_received_sii', False),
        },
        help='Automatically send AEAT Received SII reports by cron')
    not_allow_out_invoices_aeat_sii_keys = fields.Boolean(
        'Not allow post out invoices without AEAT SII Keys')
    not_allow_in_invoices_aeat_sii_keys = fields.Boolean(
        'Not allow post in invoices without AEAT SII Keys')
    sii_default_offset_days = fields.Integer('SII Default Offset Days',
        help='Default offset days in the invoices search for the SII Books',
        domain=[
            ('sii_default_offset_days', '>=', 0),
            ('sii_default_offset_days', '<=', 4),
            ],)


class TemplateTax(metaclass=PoolMeta):
    __name__ = 'account.tax.template'

    sii_book_key = fields.Selection(BOOK_KEY, 'Book Key')
    sii_operation_key = fields.Selection(OPERATION_KEY, 'SII Operation Key')
    sii_issued_key = fields.Selection(SEND_SPECIAL_REGIME_KEY, 'Issued Key')
    sii_received_key = fields.Selection(RECEIVE_SPECIAL_REGIME_KEY,
        'Received Key')
    sii_subjected_key = fields.Selection(IVA_SUBJECTED, 'Subjected Key')
    sii_exemption_cause = fields.Selection(EXEMPTION_CAUSE, 'Exemption Cause')
    sii_tax_used = fields.Boolean('Used in Tax')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        exist_sii_excemption_key = table.column_exist('sii_excemption_key')
        rename_tax_used = (table.column_exist('tax_used')
            and not table.column_exist('sii_tax_used'))
        if rename_tax_used:
            table.column_rename('tax_used', 'sii_tax_used')

        super().__register__(module_name)

        if exist_sii_excemption_key:
            # Don't use UPDATE FROM because SQLite nor MySQL support it.
            cursor.execute(*sql_table.update([sql_table.sii_exemption_cause],
                    [sql_table.sii_excemption_key])),
            table.drop_column('sii_excemption_key')

        table.drop_column('sii_intracomunity_key')
        table.drop_column('invoice_used')

    def _get_tax_value(self, tax=None):
        res = super()._get_tax_value(tax)
        for field in ('sii_book_key', 'sii_operation_key', 'sii_issued_key',
                'sii_subjected_key', 'sii_exemption_cause', 'sii_received_key',
                'sii_tax_used'):

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
    sii_tax_used = fields.Boolean('Used in Tax')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        exist_sii_excemption_key = table.column_exist('sii_excemption_key')

        rename_tax_used = (table.column_exist('tax_used')
            and not table.column_exist('sii_tax_used'))
        if rename_tax_used:
            table.column_rename('tax_used', 'sii_tax_used')

        super().__register__(module_name)

        if exist_sii_excemption_key:
            # Don't use UPDATE FROM because SQLite nor MySQL support it.
            cursor.execute(*sql_table.update([sql_table.sii_exemption_cause],
                    [sql_table.sii_excemption_key])),
            table.drop_column('sii_excemption_key')

        table.drop_column('sii_intracomunity_key')
        table.drop_column('invoice_used')

