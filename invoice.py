# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from sql.aggregate import Max

from .aeat import (
    OPERATION_KEY, BOOK_KEY, SEND_SPECIAL_REGIME_KEY,
    RECEIVE_SPECIAL_REGIME_KEY, AEAT_INVOICE_STATE, IVA_SUBJECTED,
    EXCEMPTION_CAUSE, INTRACOMUNITARY_TYPE, COMMUNICATION_TYPE)


__all__ = ['Invoice', 'Sale', 'Purchase']

_SII_INVOICE_KEYS = ['sii_book_key', 'sii_issued_key', 'sii_received_key',
        'sii_subjected_key', 'sii_excemption_key',
        'sii_intracomunity_key']


class Invoice:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice'

    sii_book_key = fields.Selection(BOOK_KEY, 'SII Book Key')
    sii_operation_key = fields.Selection(OPERATION_KEY, 'SII Operation Key')
    sii_issued_key = fields.Selection(SEND_SPECIAL_REGIME_KEY,
        'SII Issued Key',
        states={
            'invisible': ~Eval('sii_book_key').in_(['E']),
        }, depends=['sii_book_key'])
    sii_received_key = fields.Selection(RECEIVE_SPECIAL_REGIME_KEY,
        'SII Recived Key',
        states={
            'invisible':  ~Eval('sii_book_key').in_(['R']),
        }, depends=['sii_book_key'])
    sii_subjected_key = fields.Selection(IVA_SUBJECTED, 'Subjected')
    sii_excemption_key = fields.Selection(EXCEMPTION_CAUSE,
        'Excemption Cause')
    sii_intracomunity_key = fields.Selection(INTRACOMUNITARY_TYPE,
        'SII Intracommunity Key',
        states={
            'invisible': ~Eval('sii_book_key').in_(['U']),
        }, depends=['sii_book_key'])
    sii_records = fields.One2Many('aeat.sii.report.lines', 'invoice',
        "SII Report Lines")
    sii_state = fields.Function(fields.Selection(AEAT_INVOICE_STATE,
            'SII State'), 'get_sii_state', searcher='search_sii_state')
    sii_communication_type = fields.Function(fields.Selection(
        COMMUNICATION_TYPE, 'SII Communication Type'),
        'get_sii_state')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._check_modify_exclude += ['sii_book_key', 'sii_operation_key',
            'sii_received_key', 'sii_issued_key', 'sii_subjected_key',
            'sii_excemption_key', 'sii_intracomunity_key']

    @staticmethod
    def default_sii_operation_key():
        type_ = Transaction().context.get('type', 'out_invoice')
        if type_ in ('in_credit_note', 'out_credit_note'):
            return 'R1'
        return 'F1'

    @classmethod
    def search_sii_state(cls, name, clause):
        pool = Pool()
        SIILines = pool.get('aeat.sii.report.lines')

        table = SIILines.__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(*table.select(Max(table.id), table.invoice,
            group_by=table.invoice))

        invoices = []
        lines = []
        for id_, invoice in cursor.fetchall():
            invoices.append(invoice)
            lines.append(id_)

        is_none = False
        c = clause[-1]
        if isinstance(clause[-1], list):
            if None in clause[-1]:
                is_none = True
                c.remove(None)

        c0 = []
        if clause[-1] == None or is_none:
            c0 = [('id', 'not in', invoices)]

        clause2 = [tuple(('state',)) + tuple(clause[1:])] + \
                [('id', 'in', lines)]

        res_lines = SIILines.search(clause2)

        if is_none:
            return ['OR', c0, [('id', 'in', [x.invoice.id for x in res_lines])]]
        else:
            return [('id', 'in', [x.invoice.id for x in res_lines])]

    @classmethod
    def get_sii_state(cls, invoices, names):
        pool = Pool()
        SIILines = pool.get('aeat.sii.report.lines')
        SIIReport = pool.get('aeat.sii.report')

        result = {}
        for name in names:
            result[name] = dict((i.id, None) for i in invoices)

        table = SIILines.__table__()
        report = SIIReport.__table__()
        cursor = Transaction().connection.cursor()
        join = table.join(report, condition=table.report == report.id)

        cursor.execute(*table.select(Max(table.id), table.invoice,
            where=(table.invoice.in_([x.id for x in invoices]) &
                (table.state != None)),
            group_by=table.invoice))

        lines = [a[0] for a in cursor.fetchall()]

        if lines:
            cursor.execute(*join.select(table.state, report.operation_type,
                table.invoice,
                where=(table.id.in_(lines)) & (table.state != None)))

            for state, op, inv in cursor.fetchall():
                if 'sii_state' in names:
                    result['sii_state'][inv] = state
                if 'sii_communication_type' in names:
                    result['sii_communication_type'][inv] = op

        return result

    def _credit(self):
        res = super(Invoice, self)._credit()
        for field in _SII_INVOICE_KEYS:
            res[field] = getattr(self, field)

        res['sii_operation_key'] = 'R4'
        return res

    @fields.depends(*_SII_INVOICE_KEYS)
    def _on_change_lines_taxes(self):
        super(Invoice, self)._on_change_lines_taxes()
        for field in _SII_INVOICE_KEYS:
            if getattr(self, field):
                return

        tax = self.taxes and self.taxes[0]
        if not tax:
            return
        for field in _SII_INVOICE_KEYS:
            setattr(self, field, getattr(tax.tax, field))

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['sii_records'] = None
        return super(Invoice, cls).copy(records, default=default)


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'

    def create_invoice(self):
        invoice = super(Sale, self).create_invoice()
        if not invoice:
            return

        tax = invoice.taxes and invoice.taxes[0]
        if not tax:
            return invoice

        for field in _SII_INVOICE_KEYS:
            setattr(invoice, field, getattr(tax.tax, field))
        invoice.save()

        return invoice


class Purchase:
    __metaclass__ = PoolMeta
    __name__ = 'purchase.purchase'

    def create_invoice(self):
        invoice = super(Purchase, self).create_invoice()
        if not invoice:
            return

        tax = invoice.taxes and invoice.taxes[0]
        if not tax:
            return invoice

        for field in _SII_INVOICE_KEYS:
            setattr(invoice, field, getattr(tax.tax, field))
        invoice.save()

        return invoice
