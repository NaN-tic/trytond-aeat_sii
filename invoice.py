# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from sql.aggregate import Max
from trytond.tools import grouped_slice
from .aeat import (
    OPERATION_KEY, BOOK_KEY, SEND_SPECIAL_REGIME_KEY,
    RECEIVE_SPECIAL_REGIME_KEY, AEAT_INVOICE_STATE, IVA_SUBJECTED,
    EXCEMPTION_CAUSE, INTRACOMUNITARY_TYPE, COMMUNICATION_TYPE)

__all__ = ['Invoice', 'Sale', 'Purchase']

_SII_INVOICE_KEYS = ['sii_book_key', 'sii_issued_key', 'sii_received_key',
        'sii_subjected_key', 'sii_excemption_key',
        'sii_intracomunity_key']

MAX_SII_LINES = 300


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
    sii_state = fields.Selection(AEAT_INVOICE_STATE,
            'SII State', readonly=True)
    sii_communication_type = fields.Selection(
        COMMUNICATION_TYPE, 'SII Communication Type', readonly=True)
    sii_pending_sending = fields.Boolean('SII Pending Sending Pending',
            readonly=True)
    sii_header = fields.Text('Header')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        sii_fields = ['sii_book_key', 'sii_operation_key',
            'sii_received_key', 'sii_issued_key', 'sii_subjected_key',
            'sii_excemption_key', 'sii_intracomunity_key','sii_pending_sending',
            'sii_communication_type', 'sii_state', 'sii_header']
        cls._check_modify_exclude += sii_fields
        cls._error_messages.update({
            'invoices_sii': ('The next invoices are related with SII books:\n'
                '%s.\n\nIf you edit them take care if you need to update '
                'again to SII'),
            'invoices_sii_pending': ('The next invoices are related with SII '
                'books on draft state.'),
            })

        cls._buttons.update({
            'reset_sii_keys': {
                'invisible': Eval('sii_state', None) != None,
                'icon': 'tryton-executable'}
        })
        if hasattr(cls, '_intercompany_excluded_fields'):
            cls._intercompany_excluded_fields += sii_fields
            cls._intercompany_excluded_fields += ['sii_records']

    @staticmethod
    def default_sii_pending_sending():
        return False

    @classmethod
    def get_issued_sii_reports(cls):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        SIIReportLine = pool.get('aeat.sii.report.lines')

        issued_invoices = {
            'A0': {}, # 'A0', 'Registration of invoices/records'
            'A1': {}, # 'A1', 'Amendment of invoices/records (registration errors)'
            'D0': {}, # 'D0', 'Delete Invoices'
        }

        issued_invs = Invoice.search([
                ('sii_pending_sending', '=', True),
                ('sii_state', '=', 'Correcto'),
                ('sii_header', '!=', None),
                ('type', '=', 'out'),
                ])

        # search issued invoices [delete]
        delete_issued_invoices = []
        # search issued invoices [modify]
        modify_issued_invoices = []
        for issued_inv in issued_invs:
            if not issued_inv.sii_records:
                continue
            sii_record_id = max([s.id for s in issued_inv.sii_records])
            sii_record = SIIReportLine(sii_record_id)
            if issued_inv.sii_header:
                if issued_inv.sii_header != sii_record.sii_header:
                    delete_issued_invoices.append(issued_inv)
                elif issued_inv.sii_header == sii_record.sii_header:
                    modify_issued_invoices.append(issued_inv)

        delete_periods = {}
        for invoice in delete_issued_invoices:
            period = invoice.move.period
            if period in delete_periods:
                delete_periods[period].append(invoice,)
            else:
                delete_periods[period] = [invoice]
        issued_invoices['D0'] = delete_periods

        modify_periods = {}
        for invoice in modify_issued_invoices:
            period = invoice.move.period
            if period in modify_periods:
                modify_periods[period].append(invoice,)
            else:
                modify_periods[period] = [invoice]
        issued_invoices['A1'] = modify_periods

        # search issued invoices [new]
        new_issued_invoices = Invoice.search([
                ('sii_state', 'in', (None, 'Incorrecto')),
                ('sii_pending_sending', '=', True),
                ('type', '=', 'out'),
                ])

        # search possible deleted invoices in SII and not uploaded again
        new_issued_invoices += Invoice.search([
                ('sii_state', '=', 'Anulada'),
                ('sii_pending_sending', '=', True),
                ('type', '=', 'out'),
                ('state', 'in', ['paid', 'posted']),
                ])

        new_issued_invoices += delete_issued_invoices

        issued_periods = {}
        for invoice in new_issued_invoices:
            period = invoice.move.period
            if period in issued_periods:
                issued_periods[period].append(invoice,)
            else:
                issued_periods[period] = [invoice]
        issued_invoices['A0'] = issued_periods

        book_type = 'E'  # Issued
        return cls.create_sii_book(issued_invoices, book_type)

    @classmethod
    def get_received_sii_reports(cls):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        SIIReportLine = pool.get('aeat.sii.report.lines')

        received_invoices = {
            'A0': {}, # 'A0', 'Registration of invoices/records'
            'A1': {}, # 'A1', 'Amendment of invoices/records (registration errors)'
            'D0': {}, # 'D0', 'Delete Invoices'
            }

        received_invs = Invoice.search([
                ('sii_pending_sending', '=', True),
                ('sii_state', '=', 'Correcto'),
                ('sii_header', '!=', None),
                ('type', '=', 'in'),
                ])
        # search received invoices [delete]
        delete_received_invoices = []
        # search received invoices [modify]
        modify_received_invoices = []
        for received_inv in received_invs:
            if not received_inv.sii_records:
                continue
            sii_record_id = max([s.id for s in received_inv.sii_records])
            sii_record = SIIReportLine(sii_record_id)
            if received_inv.sii_header:
                if received_inv.sii_header != sii_record.sii_header:
                    delete_received_invoices.append(received_inv)
                elif received_inv.sii_header == sii_record.sii_header:
                    modify_received_invoices.append(received_inv)

        delete_periods = {}
        for invoice in delete_received_invoices:
            period = invoice.move.period
            if period in delete_periods:
                delete_periods[period].append(invoice,)
            else:
                delete_periods[period] = [invoice]
        received_invoices['D0'] = delete_periods

        modify_periods = {}
        for invoice in modify_received_invoices:
            period = invoice.move.period
            if period in modify_periods:
                modify_periods[period].append(invoice,)
            else:
                modify_periods[period] = [invoice]
        received_invoices['A1'] = modify_periods

        # search received invoices [new]
        new_received_invoices = Invoice.search([
                ('sii_state', 'in', (None, 'Incorrecto')),
                ('sii_pending_sending', '=', True),
                ('type', '=', 'in'),
                ])

        # search possible deleted invoices in SII and not uploaded again
        new_received_invoices += Invoice.search([
                ('sii_state', '=', 'Anulada'),
                ('sii_pending_sending', '=', True),
                ('type', 'in', ['in_invoice', 'in_credit_note']),
                ('state', 'in', ['paid', 'posted']),
                ])

        new_received_invoices += delete_received_invoices

        received_periods = {}
        for invoice in new_received_invoices:
            period = invoice.move.period
            if period in received_periods:
                received_periods[period].append(invoice,)
            else:
                received_periods[period] = [invoice]
        received_invoices['A0'] = received_periods

        book_type = 'R'  # Received
        return cls.create_sii_book(received_invoices, book_type)

    @classmethod
    def create_sii_book(cls, book_invoices, book):
        pool = Pool()
        SIIReport = pool.get('aeat.sii.report')
        SIIReportLine = pool.get('aeat.sii.report.lines')
        Company = Pool().get('company.company')

        company = Transaction().context.get('company')
        company = Company(company)
        company_vat = company.party.sii_vat_code

        cursor = Transaction().connection.cursor()
        report_line_table = SIIReportLine.__table__()

        reports = []
        for operation in ['D0', 'A1', 'A0']:
            values = book_invoices[operation]
            delete = True if operation == 'D0' else False
            for period, invoices in values.iteritems():
                for invs in grouped_slice(invoices, MAX_SII_LINES):
                    report = SIIReport()
                    report.company = company
                    report.company_vat = company_vat
                    report.fiscalyear = period.fiscalyear
                    report.period = period
                    report.operation_type = operation
                    report.book = book
                    report.save()
                    reports.append(report)

                    values = []
                    for inv in invs:
                        sii_header = str(inv.get_sii_header(inv, delete))
                        values.append([report.id, inv.id, sii_header, company.id])

                    cursor.execute(*report_line_table.insert(
                            columns=[report_line_table.report,
                                report_line_table.invoice,
                                report_line_table.sii_header,
                                report_line_table.company],
                            values=values
                            ))

        return reports

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
                    where=((table.id.in_(lines)) & (table.state != None) &
                        (table.company == report.company))))

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

    def _set_sii_keys(self):
        tax = None
        for t in self.taxes:
            if t.tax.sii_book_key:
                tax = t.tax
                break
        if not tax:
            return
        for field in _SII_INVOICE_KEYS:
            setattr(self, field, getattr(tax, field))

    @fields.depends(*_SII_INVOICE_KEYS)
    def _on_change_lines_taxes(self):
        super(Invoice, self)._on_change_lines_taxes()
        for field in _SII_INVOICE_KEYS:
            if getattr(self, field):
                return
        self._set_sii_keys()

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['sii_records'] = None
        default['sii_operation_key'] = None
        default['sii_pending_sending'] = False
        default['sii_header'] = None
        return super(Invoice, cls).copy(records, default=default)

    @classmethod
    @ModelView.button
    def reset_sii_keys(cls, records):
        to_write = []
        for record in records:
            record._set_sii_keys()
            record.sii_operation_key = ('R1'
                if record.untaxed_amount < Decimal('0.0') else 'F1')
            to_write.extend(([record], record._save_values))

        if to_write:
            cls.write(*to_write)

    @classmethod
    def draft(cls, invoices):
        super(Invoice, cls).draft(invoices)

        invoices_sii = ''
        to_write = []
        for invoice in invoices:
            to_write.extend(([invoice], {'sii_pending_sending': False}))

            if invoice.sii_state:
                invoices_sii += '\n%s: %s' % (invoice.number, invoice.sii_state)
            for record in invoice.sii_records:
                if record.report.state == 'draft':
                    cls.raise_user_error('invoices_sii_pending')

        if invoices_sii:
            warning_name = 'invoices_sii_report'
            cls.raise_user_warning(warning_name, 'invoices_sii', invoices_sii)

        if to_write:
            cls.write(*to_write)

    @classmethod
    def post(cls, invoices):
        to_write = []
        super(Invoice, cls).post(invoices)

        for invoice in invoices:
            values = {}
            if invoice.sii_book_key:
                if not invoice.sii_operation_key:
                    values['sii_operation_key'] = ('R1'
                        if invoice.untaxed_amount < Decimal('0.0') else 'F1')
                values['sii_pending_sending'] = True
                values['sii_header'] = str(cls.get_sii_header(invoice, False))
                to_write.extend(([invoice], values))
        if to_write:
            cls.write(*to_write)

    @classmethod
    def cancel(cls, invoices):
        cls.write(invoices, {'sii_pending_sending': False})
        return super(Invoice, cls).cancel(invoices)

    @classmethod
    def get_sii_header(cls, invoice, delete):
        pool = Pool()
        IssuedMapper = pool.get('aeat.sii.issued.invoice.mapper')(pool=pool)
        ReceivedMapper = pool.get('aeat.sii.recieved.invoice.mapper')(pool=pool)

        if delete:
            rline = [x for x in invoice.sii_records if x.state == 'Correcto']
            if rline:
                return rline[0].sii_header
        if invoice.type in ['out_invoice', 'out_credit_note']:
            header = IssuedMapper.build_delete_request(invoice)
        else:
            header = ReceivedMapper.build_delete_request(invoice)
        return header


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
