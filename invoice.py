# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import hashlib
from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError, UserWarning
from trytond.wizard import Wizard, StateView, StateTransition, Button
from .aeat import (
    OPERATION_KEY, BOOK_KEY, SEND_SPECIAL_REGIME_KEY,
    RECEIVE_SPECIAL_REGIME_KEY, AEAT_INVOICE_STATE, IVA_SUBJECTED,
    EXCEMPTION_CAUSE, INTRACOMUNITARY_TYPE, COMMUNICATION_TYPE)


__all__ = ['Invoice', 'ResetSIIKeysStart', 'ResetSIIKeys', 'ResetSIIKeysEnd']

_SII_INVOICE_KEYS = ['sii_book_key', 'sii_operation_key', 'sii_issued_key',
        'sii_received_key', 'sii_subjected_key', 'sii_excemption_key',
        'sii_intracomunity_key']


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
        if hasattr(cls, '_intercompany_excluded_fields'):
            cls._intercompany_excluded_fields += sii_fields
            cls._intercompany_excluded_fields += ['sii_records']

    @staticmethod
    def default_sii_pending_sending():
        return False

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

        for invoice in invoices2checksii:
            values = {}
            if invoice.sii_book_key:
                if not invoice.sii_operation_key:
                    values['sii_operation_key'] =\
                        invoice._get_sii_operation_key()
                values['sii_pending_sending'] = True
                values['sii_header'] = str(cls.get_sii_header(invoice, False))
                to_write.extend(([invoice], values))
            if (invoice.sii_subjected_key in ('S2', 'S3') and
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
