# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import hashlib
from ast import literal_eval
from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError, UserWarning
from trytond.wizard import Wizard, StateView, StateTransition, Button
from sql import Null
from sql.aggregate import Max
from trytond.tools import grouped_slice
from .aeat import (
    OPERATION_KEY, BOOK_KEY, SEND_SPECIAL_REGIME_KEY, COMMUNICATION_TYPE,
    RECEIVE_SPECIAL_REGIME_KEY, AEAT_INVOICE_STATE)


__all__ = ['Invoice', 'ResetSIIKeysStart', 'ResetSIIKeys', 'ResetSIIKeysEnd']

_SII_INVOICE_KEYS = ['sii_book_key', 'sii_operation_key', 'sii_issued_key',
        'sii_received_key']

MAX_SII_LINES = 300


class Invoice(metaclass=PoolMeta):
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
            'invisible': ~Eval('sii_book_key').in_(['R']),
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
            'sii_received_key', 'sii_issued_key', 'sii_state',
            'sii_pending_sending', 'sii_communication_type', 'sii_header']
        cls._check_modify_exclude += sii_fields
        if hasattr(cls, '_intercompany_excluded_fields'):
            cls._intercompany_excluded_fields += sii_fields
            cls._intercompany_excluded_fields += ['sii_records']

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        exist_sii_intracomunity_key = table.column_exist('sii_intracomunity_key')
        exist_sii_subjected_key = table.column_exist('sii_subjected_key')
        exist_sii_excemption_key = table.column_exist('sii_excemption_key')

        super(Invoice, cls).__register__(module_name)

        if exist_sii_intracomunity_key:
            table.drop_column('sii_intracomunity_key')
        if exist_sii_subjected_key:
            table.drop_column('sii_subjected_key')
        if exist_sii_excemption_key:
            table.drop_column('sii_excemption_key')

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
                ('type', 'in', ['out']),
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
                if (literal_eval(issued_inv.sii_header) ==
                        literal_eval(sii_record.sii_header)):
                    modify_issued_invoices.append(issued_inv)
                else:
                    delete_issued_invoices.append(issued_inv)

        periods = {}
        for invoice in delete_issued_invoices:
            period = invoice.move.period
            if period in periods:
                periods[period].append(invoice,)
            else:
                periods[period] = [invoice]
        issued_invoices['D0'] = periods

        periods2 = {}
        for invoice in modify_issued_invoices:
            period = invoice.move.period
            if period in periods2:
                periods2[period].append(invoice,)
            else:
                periods2[period] = [invoice]
        issued_invoices['A1'] = periods2

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

        periods1 = {}
        for invoice in new_issued_invoices:
            period = invoice.move.period
            if period in periods1:
                periods1[period].append(invoice,)
            else:
                periods1[period] = [invoice]
        issued_invoices['A0'] = periods1

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
                if (literal_eval(received_inv.sii_header) ==
                        literal_eval(sii_record.sii_header)):
                    modify_received_invoices.append(received_inv)
                else:
                    delete_received_invoices.append(received_inv)

        periods2 = {}
        for invoice in modify_received_invoices:
            period = invoice.move.period
            if period in periods2:
                periods2[period].append(invoice,)
            else:
                periods2[period] = [invoice]
        received_invoices['A1'] = periods2

        periods = {}
        for invoice in delete_received_invoices:
            period = invoice.move.period
            if period in periods:
                periods[period].append(invoice,)
            else:
                periods[period] = [invoice]
        received_invoices['D0'] = periods

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
                ('type', '=', 'in'),
                ('state', 'in', ['paid', 'posted']),
                ])

        new_received_invoices += delete_received_invoices

        periods1 = {}
        for invoice in new_received_invoices:
            period = invoice.move.period
            if period in periods1:
                periods1[period].append(invoice,)
            else:
                periods1[period] = [invoice]
        received_invoices['A0'] = periods1

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
            for period, invoices in values.items():
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
                (table.state != Null)),
            group_by=table.invoice))

        lines = [a[0] for a in cursor.fetchall()]

        if lines:
            cursor.execute(*join.select(table.state, report.operation_type,
                    table.invoice,
                    where=((table.id.in_(lines)) & (table.state != Null) &
                        (table.company == report.company))))

            for state, op, inv in cursor.fetchall():
                if 'sii_state' in names:
                    result['sii_state'][inv] = state
                if 'sii_communication_type' in names:
                    result['sii_communication_type'][inv] = op

        return result

    def _credit(self):
        credit = super(Invoice, self)._credit()
        for field in _SII_INVOICE_KEYS:
            setattr(credit, field, getattr(self, field))

        credit.sii_operation_key = 'R1'
        return credit

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
        default.setdefault('sii_records')
        default.setdefault('sii_state')
        default.setdefault('sii_communication_type')
        default.setdefault('sii_operation_key')
        default.setdefault('sii_pending_sending')
        default.setdefault('sii_header')
        return super(Invoice, cls).copy(records, default=default)

    def _get_sii_operation_key(self):
        return 'R1' if self.untaxed_amount < Decimal('0.0') else 'F1'

    @classmethod
    def reset_sii_keys(cls, invoices):
        to_write = []
        for invoice in invoices:
            if invoice.state != 'draft':
                continue
            for field in _SII_INVOICE_KEYS:
                setattr(invoice, field, None)
            invoice._set_sii_keys()
            if not invoice.sii_operation_key:
                invoice.sii_operation_key = invoice._get_sii_operation_key()
            to_write.extend(([invoice], invoice._save_values))

        if to_write:
            cls.write(*to_write)

    @classmethod
    def process(cls, invoices):
        super(Invoice, cls).process(invoices)
        invoices_sii = ''
        for invoice in invoices:
            if invoice.state != 'draft':
                continue
            if invoice.sii_state:
                invoices_sii += '\n%s: %s' % (invoice.number, invoice.sii_state)
        if invoices_sii:
            raise UserError(gettext('aeat_sii.msg_invoices_sii',
                invoices=invoices_sii))

    @classmethod
    def draft(cls, invoices):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        super(Invoice, cls).draft(invoices)
        invoices_sii = []
        to_write = []
        for invoice in invoices:
            to_write.extend(([invoice], {'sii_pending_sending': False}))

            if invoice.sii_state:
                invoices_sii.append('%s: %s' % (
                    invoice.number, invoice.sii_state))
            for record in invoice.sii_records:
                if record.report.state == 'draft':
                    raise UserError(gettext('aeat_sii.invoices_sii_pending'))

        if invoices_sii:
            warning_name = 'invoices_sii.' + hashlib.md5(
                ''.join(invoices_sii).encode('utf-8')).hexdigest()
            if Warning.check(warning_name):
                raise UserWarning(warning_name,
                        gettext('aeat_sii.msg_invoices_sii',
                        invoices='\n'.join(invoices_sii)))

        if to_write:
            cls.write(*to_write)

    @classmethod
    def post(cls, invoices):
        to_write = []

        invoices2checksii = []
        for invoice in invoices:
            if not invoice.move or invoice.move.state == 'draft':
                invoices2checksii.append(invoice)

        super(Invoice, cls).post(invoices)

        #TODO:
        # OUT invoice, check that all tax have the same TipoNoExenta and(or the same Exenta
        # Suejta-Exenta --> Can only be one
        # NoSujeta --> Can only be one

        for invoice in invoices2checksii:
            values = {}
            if invoice.sii_book_key:
                if not invoice.sii_operation_key:
                    values['sii_operation_key'] =\
                        invoice._get_sii_operation_key()
                values['sii_pending_sending'] = True
                values['sii_header'] = str(cls.get_sii_header(invoice, False))
                to_write.extend(([invoice], values))
            for tax in invoice.taxes:
                if (tax.tax.sii_subjected_key in ('S2', 'S3') and
                        not invoice.sii_operation_key in (
                            'F1', 'R1', 'R2', 'R3', 'R4')):
                    raise UserError(gettext('aeat_sii.msg_sii_operation_key_wrong',
                        invoice=invoice))
        if to_write:
            cls.write(*to_write)

    @classmethod
    def cancel(cls, invoices):
        cls.write(invoices, {'sii_pending_sending': False})
        return super(Invoice, cls).cancel(invoices)

    @classmethod
    def get_sii_header(cls, invoice, delete):
        pool = Pool()
        IssuedMapper = pool.get('aeat.sii.issued.invoice.mapper')
        ReceivedMapper = pool.get('aeat.sii.recieved.invoice.mapper')

        if delete:
            rline = [x for x in invoice.sii_records if x.state == 'Correcto'
                and x.sii_header != None]
            if rline:
                return rline[0].sii_header
        if invoice.type == 'out':
            mapper = IssuedMapper()
            header = mapper.build_delete_request(invoice)
        else:
            mapper = ReceivedMapper()
            header = mapper.build_delete_request(invoice)
        return header


class ResetSIIKeysStart(ModelView):
    """
    Reset to default SII Keys Start
    """
    __name__ = "aeat.sii.reset.keys.start"


class ResetSIIKeysEnd(ModelView):
    """
    Reset to default SII Keys End
    """
    __name__ = "aeat.sii.reset.keys.end"


class ResetSIIKeys(Wizard):
    """
    Reset to default SII Keys
    """
    __name__ = "aeat.sii.reset.keys"

    start = StateView('aeat.sii.reset.keys.start',
        'aeat_sii.aeat_sii_reset_keys_start_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Reset', 'reset', 'tryton-ok', default=True),
            ])
    reset = StateTransition()
    done = StateView('aeat.sii.reset.keys.end',
        'aeat_sii.aeat_sii_reset_keys_end_view', [
            Button('Ok', 'end', 'tryton-ok', default=True),
            ])

    def transition_reset(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoices = Invoice.browse(Transaction().context['active_ids'])
        Invoice.reset_sii_keys(invoices)
        return 'done'
