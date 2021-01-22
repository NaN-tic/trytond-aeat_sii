# -*- coding: utf-8 -*-
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unicodedata
from logging import getLogger
from decimal import Decimal
from datetime import datetime
from zeep import helpers
import json
from collections import namedtuple

from trytond.model import ModelSQL, ModelView, fields, Workflow
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import Eval, Bool, PYSONEncoder
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.config import config
from trytond.i18n import gettext
from trytond.exceptions import UserError
from . import tools
from . import service


__all__ = [
    'SIIReport',
    'SIIReportLine',
    'SIIReportLineTax',
    'CreateSiiIssuedPendingView',
    'CreateSiiIssuedPending',
    'CreateSiiReceivedPendingView',
    'CreateSiiReceivedPending',
]

_logger = getLogger(__name__)
_ZERO = Decimal('0.0')

# AEAT SII test
SII_TEST = config.getboolean('aeat', 'sii_test', default=True)


def _decimal(x):
    return Decimal(x) if x is not None else None


def _date(x):
    return datetime.strptime(x, "%d-%m-%Y").date()


def _datetime(x):
    return datetime.strptime(x, "%d-%m-%Y %H:%M:%S")

COMMUNICATION_TYPE = [   # L0
    (None, ''),
    ('A0', 'Registration of invoices/records'),
    ('A1', 'Amendment of invoices/records (registration errors)'),
    # ('A4', 'Amendment of Invoice for Travellers'), # Not supported
    # ('A5', 'Travellers registration'), # Not supported
    # ('A6', 'Amendment of travellers tax devolutions'), # Not supported
    ('C0', 'Query Invoices'),  # Not in L0
    ('D0', 'Delete Invoices'),  # Not In L0
    ]

BOOK_KEY = [
    (None, ''),
    ('E', 'Issued Invoices'),
    ('I', 'Investment Goods'),
    ('R', 'Received Invoices'),
    ('U', 'Particular Intracommunity Operations'),
    ]

# R1: errores fundados de derecho y causas del artículo 80.Uno, Dos y Seis LIVA
# R2: concurso de acreedores
# R3: deudas incobrables
# R4: resto de causas
OPERATION_KEY = [    # L2_EMI - L2_RECI
    (None, ''),
    ('F1', 'Invoice (Art 6.7.3 y 7.3 of RD1619/2012)'),
    ('F2', 'Simplified Invoice (ticket) and Invoices without destination '
        'identidication (Art 6.1.d of RD1619/2012)'),
    ('R1', 'Corrected Invoice '
        '(Art 80.1, 80.2 and 80.6 and error grounded in law)'),
    ('R2', 'Corrected Invoice (Art. 80.3)'),
    ('R3', 'Credit Note (Art 80.4)'),
    ('R4', 'Corrected Invoice (Other)'),
    ('R5', 'Corrected Invoice in simplified invoices'),
    ('F3', 'Invoice issued to replace simplified invoices issued and filed'),
    ('F4', 'Invoice summary entry'),
    ('F5', 'Import (DUA)'),
    ('F6', 'Other accounting documents'),
    ('LC', 'Duty - Complementary clearing'), # Not supported
    ]

PARTY_IDENTIFIER_TYPE = [
    (None, ''),
    ('02', 'VAT (only for intracommunity operators)'),
    ('03', 'Passport'),
    ('04', 'Official identification document issued by the country '
        'or region of residence'),
    ('05', 'Residence certificate'),
    ('06', 'Other supporting document'),
    ('07', 'Not registered (only for Spanish VAT not registered)'),
    ]

SEND_SPECIAL_REGIME_KEY = [  # L3.1
    (None, ''),
    ('01', 'General tax regime activity'),
    ('02', 'Export'),
    ('03', 'Activities to which the special scheme of used goods, '
        'works of art, antiquities and collectables (135-139 of the VAT Law)'),
    ('04', 'Special scheme for investment gold'),
    ('05', 'Special scheme for travel agencies'),
    ('06', 'Special scheme applicable to groups of entities, VAT (Advanced)'),
    ('07', 'Special cash basis scheme'),
    ('08', 'Activities subject to Canary Islands General Indirect Tax/Tax on '
        'Production, Services and Imports'),
    ('09', 'Invoicing of the provision of travel agency services acting as '
        'intermediaries in the name of and on behalf of other persons '
        '(Additional Provision 4, Royal Decree 1619/2012)'),
    ('10', 'Collections on behalf of third parties of professional fees or '
        'industrial property, copyright or other such rights by partners, '
        'associates or members undertaken by companies, associations, '
        'professional organisations or other entities that, amongst their '
        'functions, undertake collections'),
    ('11', 'Business premises lease activities subject to withholding'),
    ('12', 'Business premises lease activities not subject to withholding'),
    ('13', 'Business premises lease activities subject and not subject '
        'to withholding'),
    ('14', 'Invoice with VAT pending accrual (work certifications with Public '
        'Administration recipients)'),
    ('15', 'Invoice with VAT pending accrual - '
        'operations of successive tract'),
    ('16', 'First semester 2017 and other invoices before the SII'),
    ]

RECEIVE_SPECIAL_REGIME_KEY = [
    (None, ''),
    ('01', 'General tax regime activity'),
    ('02', 'Activities through which businesses pay compensation for special '
        'VAT arrangements for agriculture and fisheries'),
    ('03', 'Activities to which the special scheme of used goods, '
        'works of art, antiquities and collectables (135-139 of the VAT Law)'),
    ('04', 'Special scheme for investment gold'),
    ('05', 'Special scheme for travel agencies'),
    ('06', 'Special scheme applicable to groups of entities, VAT (Advanced)'),
    ('07', 'Special cash basis scheme'),
    ('08', 'Activities subject to Canary Islands General Indirect Tax/Tax '
        'on Production, Services and Imports'),
    ('09', 'Intra-Community acquisition of assets and provisions of services'),
    ('12', 'Business premises lease activities'),
    ('13', 'Invoice corresponding to an import '
        '(reported without been associated with a DUA)'),
    ('14', 'First semester 2017 and other invoices before the SII'),
    ]

AEAT_COMMUNICATION_STATE = [
    (None, ''),
    ('Correcto', 'Accepted'),
    ('ParcialmenteCorrecto', 'Partially Accepted'),
    ('Incorrecto', 'Rejected')
    ]

AEAT_INVOICE_STATE = [
    (None, ''),
    ('Correcto', 'Accepted '),
    ('Correcta', 'Accepted'),  # You guys are disgusting
    ('AceptadoConErrores', 'Accepted with Errors '),
    ('AceptadaConErrores', 'Accepted with Errors'),  # Shame on AEAT
    ('Anulada', 'Deleted'),
    ('Incorrecto', 'Rejected'),
    ('duplicated_unsubscribed', 'Duplicated / Unsubscribed'),
]

PROPERTY_STATE = [  # L6
    ('0', ''),
    ('1', '1. Property with a land register reference located in any part '
        'of Spain, with the exception of the Basque Country and Navarre'),
    ('2', '2. Property located in the Autonomous Community of the Basque '
        'Country or the Chartered Community of Navarre.'),
    ('3', '3. Property in any of the foregoing locations '
        'with no land register reference'),
    ('4', '4. Property located abroad'),
    ]

# L7 - Iva Subjected
IVA_SUBJECTED = [
    (None, ''),
    ('S1', 'Subject - Not exempt. Non VAT reverse charge'),
    ('S2', 'Subject - Not exempt. VAT reverse charge'),
    ('S3', 'Subject - Not exempt. Both non VAT reverse charge '
        'and VAT reverse charge')
    ]

# L9 - Exemption cause
EXEMPTION_CAUSE = [
    (None, ''),
    ('E1', 'Exempt on account of Article 20'),
    ('E2', 'Exempt on account of Article 21'),
    ('E3', 'Exempt on account of Article 22'),
    ('E4', 'Exempt on account of Article 23 and Article 24'),
    ('E5', 'Exempt on account of Article 25'),
    ('E6', 'Exempt on other grounds'),
    ('NotSubject', 'Not Subject'),
    ]

_STATES = {
    'readonly': Eval('state') != 'draft',
    }
_DEPENDS = ['state']


class SIIReport(Workflow, ModelSQL, ModelView):
    ''' SII Report '''
    __name__ = 'aeat.sii.report'
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') != 'draft',
        }, depends=['state'])
    company_vat = fields.Char('VAT', size=9,
        states={
            'required': Eval('state').in_(['confirmed', 'done']),
            'readonly': ~Eval('state').in_(['draft', 'confirmed']),
            },
        depends=['state'])
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'on_change_with_currency')
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True, states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('fiscalyear'))),
        }, depends=['state'])
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[('fiscalyear', '=', Eval('fiscalyear'))],
        states={
            'readonly': ((Eval('state') != 'draft')
                | (Eval('lines', [0]) & Eval('period'))),
        }, depends=['state', 'fiscalyear'])
    load_date = fields.Date('Load Date',
        domain=['OR', [
                    ('load_date', '=', None),
                ], [
                    ('load_date', '>=', Eval('load_date_start')),
                    ('load_date', '<=', Eval('load_date_end')),
                ]
        ], depends=['load_date_start', 'load_date_end'],
        help='Filter invoices to the date whitin the period.')
    load_date_start = fields.Function(fields.Date('Load Date Start'),
        'on_change_with_load_date_start')
    load_date_end = fields.Function(fields.Date('Load Date End'),
        'on_change_with_load_date_end')
    operation_type = fields.Selection(COMMUNICATION_TYPE, 'Operation Type',
        required=True,
        states={
            'readonly': ((~Eval('state').in_(['draft', 'confirmed']))
                | (Eval('lines', [0]) & Eval('operation_type'))),
        }, depends=['state'])
    book = fields.Selection(BOOK_KEY, 'Book', required=True,
        states={
            'readonly': ((~Eval('state').in_(['draft', 'confirmed']))
                | (Eval('lines', [0]) & Eval('book'))),
        }, depends=['state'])
    state = fields.Selection([
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('sending', 'Sending'),
            ('cancelled', 'Cancelled'),
            ('sent', 'Sent'),
        ], 'State', readonly=True)
    communication_state = fields.Selection(AEAT_COMMUNICATION_STATE,
        'Communication State', readonly=True)
    csv = fields.Char('CSV', readonly=True)
    version = fields.Selection([
            ('0.7', '0.7'),
            ('1.0', '1.0'),
            ('1.1', '1.1'),
            ], 'Version', required=True, readonly=True)
    lines = fields.One2Many('aeat.sii.report.lines', 'report',
        'Lines', states={
            'readonly': Eval('state') != 'draft',
        }, depends=['state'])
    # TODO crash GTK client 4.x with widget date in XML view and attribute
    # readonly = True. At the moment, use PYSON to readonly field in XML views.
    send_date = fields.DateTime('Send date',
        states={
            'invisible': Eval('state') != 'sent',
            'readonly': Bool(Eval('state') == 'sent'),
        },
        depends=['state'])
    response = fields.Text('Response', readonly=True)
    aeat_register = fields.Text('Register sended to AEAT Webservice', readonly=True)

    @classmethod
    def __setup__(cls):
        super(SIIReport, cls).__setup__()
        cls._buttons.update({
                'draft': {
                    'invisible': ~Eval('state').in_(['confirmed',
                            'cancelled']),
                    'icon': 'tryton-go-previous',
                    },
                'confirm': {
                    'invisible': ~Eval('state').in_(['draft']),
                    'icon': 'tryton-go-next',
                    },
                'send': {
                    'invisible': ~Eval('state').in_(['confirmed']),
                    'icon': 'tryton-ok',
                    },
                'cancel': {
                    'invisible': Eval('state').in_(['cancelled', 'sent']),
                    'icon': 'tryton-cancel',
                    },
                'load_invoices': {
                    'invisible': ~(Eval('state').in_(['draft']) &
                         Eval('operation_type').in_(['A0', 'A1'])),
                    },
                'process_response': {
                    'invisible': ~Eval('state').in_(['sending']),
                    }
                })

        cls._transitions |= set((
                ('draft', 'confirmed'),
                ('draft', 'cancelled'),
                ('confirmed', 'draft'),
                ('confirmed', 'sent'),
                ('confirmed', 'cancelled'),
                ('sending', 'sent'),
                ('cancelled', 'draft'),
                ))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_version():
        return '1.1'

    @fields.depends('period')
    def on_change_period(self):
        if not self.period:
            self.load_date = None

    @fields.depends('company')
    def on_change_with_company_vat(self):
        if self.company:
            return self.company.party.sii_vat_code

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company:
            return self.company.currency.id

    @fields.depends('period')
    def on_change_with_load_date_start(self, name=None):
        return self.period.start_date if self.period else None

    @fields.depends('period')
    def on_change_with_load_date_end(self, name=None):
        return self.period.end_date if self.period else None

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['communication_state'] = None
        default['csv'] = None
        default['send_date'] = None
        return super(SIIReport, cls).copy(records, default=default)

    @classmethod
    def delete(cls, reports):
        # Cancel before delete
        for report in reports:
            if report.state != 'cancelled':
                raise UserError(gettext('aeat_sii.msg_delete_cancel',
                    report=report.rec_name))
        super(SIIReport, cls).delete(reports)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, reports):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, reports):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, reports):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('sent')
    def send(cls, reports):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        for report in reports:
            if report.state != 'confirmed':
                continue
            if report.book == 'E':  # issued invoices
                if report.operation_type in {'A0', 'A1'}:
                    report.submit_issued_invoices()
                elif report.operation_type == 'C0':
                    report.query_issued_invoices()
                elif report.operation_type == 'D0':
                    report.delete_issued_invoices()
                else:
                    raise NotImplementedError
            elif report.book == 'R':
                if report.operation_type in {'A0', 'A1'}:
                    report.submit_recieved_invoices()
                elif report.operation_type == 'C0':
                    report.query_recieved_invoices()
                elif report.operation_type == 'D0':
                    report.delete_recieved_invoices()
                else:
                    raise NotImplementedError
            else:
                raise NotImplementedError

        to_save = []
        for report in reports:
            if report.operation_type == 'C0':
                continue
            for line in report.lines:
                invoice = line.invoice
                if invoice:
                    invoice.sii_communication_type = report.operation_type
                    invoice.sii_state = line.state

                    to_save.append(invoice)

        Invoice.save(to_save)
        cls.write(reports, {
            'send_date': datetime.now(),
            })
        _logger.debug('Done sending reports to AEAT SII')

    @classmethod
    @ModelView.button
    @Workflow.transition('sent')
    def process_response(cls, reports):
        for report in reports:
            if report.response:
                cls._save_response(report.response)
                report.save()

    @classmethod
    @ModelView.button
    def load_invoices(cls, reports):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ReportLine = pool.get('aeat.sii.report.lines')

        to_create = []
        for report in reports:
            domain = [
                ('sii_book_key', '=', report.book),
                ('move.period', '=', report.period.id),
                ('state', 'in', ['posted', 'paid']),
            ]

            if report.operation_type == 'A0':
                domain.append(('sii_state', 'in', [None, 'Incorrecto']))

            elif report.operation_type in ('A1', 'A4'):
                domain.append(('sii_state', 'in', [
                    'AceptadoConErrores', 'AceptadaConErrores']))

            if report.load_date:
                domain.append(['OR', [
                        ('invoice_date', '<=', report.load_date),
                        ('accounting_date', '=', None),
                        ], [
                        ('accounting_date', '<=', report.load_date),
                        ]])

            _logger.debug('Searching invoices for SII report: %s', domain)

            for invoice in Invoice.search(domain):
                if not all(l.report != report for l in invoice.sii_records):
                    continue
                to_create.append({
                    'report': report,
                    'invoice': invoice,
                    })

        if to_create:
            ReportLine.create(to_create)

    def submit_issued_invoices(self):
        if self.state != 'confirmed':
            _logger.info('This report %s has already been sended', self.id)
        else:
            _logger.info('Sending report %s to AEAT SII', self.id)
            headers = tools.get_headers(
                name=tools.unaccent(self.company.party.name),
                vat=self.company_vat,
                comm_kind=self.operation_type,
                version=self.version)

            with self.company.tmp_ssl_credentials() as (crt, key):
                srv = service.bind_issued_invoices_service(
                    crt, key, test=SII_TEST)
                try:
                    res, request = srv.submit(headers, (l.invoice for l in self.lines))
                    self.aeat_register = request
                except Exception as e:
                    raise UserError(tools.unaccent(str(e)))

            if not self.response:
                self.state == 'sending'
                self.response = json.dumps(helpers.serialize_object(res))
                self.save()
                Transaction().commit()
        self._save_response(self.response)

    def delete_issued_invoices(self):
        if self.state != 'confirmed':
            _logger.info('This report %s has already been sended', self.id)
        else:
            _logger.info('Deleting report %s from AEAT SII', self.id)
            headers = tools.get_headers(
                name=tools.unaccent(self.company.party.name),
                vat=self.company_vat,
                comm_kind=self.operation_type,
                version=self.version)

            with self.company.tmp_ssl_credentials() as (crt, key):
                srv = service.bind_issued_invoices_service(
                    crt, key, test=SII_TEST)
                try:
                    res = srv.cancel(
                        headers, [eval(line.sii_header) for line in self.lines])
                except Exception as e:
                    raise UserError(gettext('aeat_sii.msg_service_message',
                        message=tools.unaccent(str(e))))

            if not self.response:
                self.state == 'sending'
                self.response = json.dumps(helpers.serialize_object(res))
                self.save()
                Transaction().commit()
        self._save_response(self.response)

    def query_issued_invoices(self, last_invoice=None):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        SIIReportLine = pool.get('aeat.sii.report.lines')
        SIIReportLineTax = pool.get('aeat.sii.report.line.tax')

        headers = tools.get_headers(
            name=tools.unaccent(self.company.party.name),
            vat=self.company_vat,
            comm_kind=self.operation_type,
            version=self.version)

        with self.company.tmp_ssl_credentials() as (crt, key):
            srv = service.bind_issued_invoices_service(
                crt, key, test=SII_TEST)
            res = srv.query(
                headers,
                year=self.period.start_date.year,
                period=self.period.start_date.month,
                last_invoice=last_invoice)

        registers = res.RegistroRespuestaConsultaLRFacturasEmitidas
        # FIXME: the number can be repeated over time
        invoices_list = Invoice.search([
                ('number', 'in', [
                    reg.IDFactura.NumSerieFacturaEmisor
                    for reg in registers
                    ]),
                ('state', 'in', ('posted', 'paid')),
                ])
        invoices_ids = {
            invoice.number: invoice.id
            for invoice in invoices_list
        }
        pagination = res.IndicadorPaginacion
        last_invoice = registers and registers[-1].IDFactura
        lines_to_create = []
        for reg in registers:
            taxes_to_create = []
            taxes = None
            exemption = ''
            tipo_desglose = reg.DatosFacturaEmitida.TipoDesglose
            if tipo_desglose.DesgloseFactura:
                sujeta = tipo_desglose.DesgloseFactura.Sujeta
            else:
                if tipo_desglose.DesgloseTipoOperacion.PrestacionServicios:
                    sujeta = tipo_desglose.DesgloseTipoOperacion.\
                        PrestacionServicios.Sujeta
                else:
                    sujeta = tipo_desglose.DesgloseTipoOperacion.Entrega.Sujeta

            if sujeta.NoExenta:
                for detail in sujeta.NoExenta.DesgloseIVA.DetalleIVA:
                    taxes_to_create.append({
                            'base': _decimal(detail.BaseImponible),
                            'rate': _decimal(detail.TipoImpositivo),
                            'amount': _decimal(detail.CuotaRepercutida),
                            'surcharge_rate': _decimal(
                                detail.TipoRecargoEquivalencia),
                            'surcharge_amount': _decimal(
                                detail.CuotaRecargoEquivalencia),
                            })
                taxes = SIIReportLineTax.create(taxes_to_create)
            elif sujeta.Exenta:
                exemption = sujeta.Exenta.DetalleExenta[0].CausaExencion
                for exempt in EXEMPTION_CAUSE:
                    if exempt[0] == exemption:
                        exemption = exempt[1]
                        break

            sii_report_line = {
                'report': self.id,
                'invoice': invoices_ids.get(
                    reg.IDFactura.NumSerieFacturaEmisor),
                'state': reg.EstadoFactura.EstadoRegistro,
                'last_modify_date': _datetime(
                    reg.EstadoFactura.TimestampUltimaModificacion),
                'communication_code': reg.EstadoFactura.CodigoErrorRegistro,
                'communication_msg': reg.EstadoFactura.DescripcionErrorRegistro,
                'issuer_vat_number': (
                    reg.IDFactura.IDEmisorFactura.NIF or
                    reg.IDFactura.IDEmisorFactura.IDOtro.ID),
                'serial_number': reg.IDFactura.NumSerieFacturaEmisor,
                'final_serial_number': (
                    reg.IDFactura.NumSerieFacturaEmisorResumenFin),
                'issue_date': _date(
                    reg.IDFactura.FechaExpedicionFacturaEmisor),
                'invoice_kind': reg.DatosFacturaEmitida.TipoFactura,
                'special_key': (
                    reg.DatosFacturaEmitida.ClaveRegimenEspecialOTrascendencia),
                'total_amount': _decimal(reg.DatosFacturaEmitida.ImporteTotal),
                'taxes': [('add', [t.id for t in taxes])] if taxes else [],
                'exemption_cause': exemption,
                'counterpart_name': (
                    reg.DatosFacturaEmitida.Contraparte.NombreRazon
                    if reg.DatosFacturaEmitida.Contraparte else None),
                'counterpart_id': (
                    (
                        reg.DatosFacturaEmitida.Contraparte.NIF or
                        reg.DatosFacturaEmitida.Contraparte.IDOtro.ID)
                    if reg.DatosFacturaEmitida.Contraparte else None),
                'presenter': reg.DatosPresentacion.NIFPresentador,
                'presentation_date': _datetime(
                    reg.DatosPresentacion.TimestampPresentacion),
                'csv': reg.DatosPresentacion.CSV,
                'balance_state': reg.DatosPresentacion.CSV,
                'aeat_register': str(reg),
                }
            lines_to_create.append(sii_report_line)
        SIIReportLine.create(lines_to_create)

        if pagination == 'S':
            self.query_issued_invoices(last_invoice=last_invoice)

    def submit_recieved_invoices(self):
        if self.state != 'confirmed':
            _logger.info('This report %s has already been sended', self.id)
        else:
            _logger.info('Sending report %s to AEAT SII', self.id)
            headers = tools.get_headers(
                name=tools.unaccent(self.company.party.name),
                vat=self.company_vat,
                comm_kind=self.operation_type,
                version=self.version)

            with self.company.tmp_ssl_credentials() as (crt, key):
                srv = service.bind_recieved_invoices_service(
                    crt, key, test=SII_TEST)
                try:
                    res, request = srv.submit(headers, (l.invoice for l in self.lines))
                    self.aeat_register = request
                except Exception as e:
                    raise UserError(gettext('aeat_sii.msg_service_message',
                        message=tools.unaccent(str(e))))

            if not self.response:
                self.state == 'sending'
                self.response = json.dumps(helpers.serialize_object(res))
                self.save()
                Transaction().commit()
        self._save_response(self.response)

    def delete_recieved_invoices(self):
        if self.state != 'confirmed':
            _logger.info('This report %s has already been sended', self.id)
        else:
            _logger.info('Deleting report %s from AEAT SII', self.id)
            headers = tools.get_headers(
                name=tools.unaccent(self.company.party.name),
                vat=self.company_vat,
                comm_kind=self.operation_type,
                version=self.version)

            with self.company.tmp_ssl_credentials() as (crt, key):
                try:
                    srv = service.bind_recieved_invoices_service(
                        crt, key, test=SII_TEST)
                    res = srv.cancel(
                        headers, [eval(line.sii_header) for line in self.lines])
                except Exception as e:
                    raise UserError(gettext('aeat_sii.msg_service_message',
                        message=tools.unaccent(str(e))))

            if not self.response:
                self.state == 'sending'
                self.response = json.dumps(helpers.serialize_object(res))
                self.save()
                Transaction().commit()
        self._save_response(self.response)

    def _save_response(self, res):
        if res:
            response = json.loads(res, object_hook=lambda d: namedtuple(
                    'SII', d.keys())(*d.values()))
            for (report_line, response_line) in zip(
                    self.lines, response.RespuestaLinea):
                if not report_line.communication_code:
                    report_line.state = response_line.EstadoRegistro
                    report_line.communication_code = response_line.CodigoErrorRegistro
                    report_line.communication_msg = (
                        response_line.DescripcionErrorRegistro)
                    report_line.save()
            if not self.communication_state:
                self.communication_state = response.EstadoEnvio
            if not self.csv:
                self.csv = response.CSV
            self.response = ''
            self.save()

    def query_recieved_invoices(self, last_invoice=None):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        SIIReportLine = pool.get('aeat.sii.report.lines')
        SIIReportLineTax = pool.get('aeat.sii.report.line.tax')

        headers = tools.get_headers(
            name=tools.unaccent(self.company.party.name),
            vat=self.company_vat,
            comm_kind=self.operation_type,
            version=self.version)

        with self.company.tmp_ssl_credentials() as (crt, key):
            srv = service.bind_recieved_invoices_service(
                crt, key, test=SII_TEST)
            res = srv.query(
                headers,
                year=self.period.start_date.year,
                period=self.period.start_date.month,
                last_invoice=last_invoice)

        _logger.debug(res)
        registers = res.RegistroRespuestaConsultaLRFacturasRecibidas
        pagination = res.IndicadorPaginacion
        last_invoice = registers[-1].IDFactura

        # FIXME: the reference is not forced to be unique
        lines_to_create = []
        for reg in registers:
            invoice_date = _date(reg.IDFactura.FechaExpedicionFacturaEmisor)

            taxes_to_create = []
            for detail in reg.DatosFacturaRecibida.DesgloseFactura.DesgloseIVA.\
                    DetalleIVA:
                taxes_to_create.append({
                        'base': _decimal(detail.BaseImponible),
                        'rate': _decimal(detail.TipoImpositivo),
                        'amount': _decimal(detail.CuotaSoportada),
                        'surcharge_rate': _decimal(
                            detail.TipoRecargoEquivalencia),
                        'surcharge_amount': _decimal(
                            detail.CuotaRecargoEquivalencia),
                        'reagyp_rate': _decimal(
                            detail.PorcentCompensacionREAGYP),
                        'reagyp_amount': _decimal(
                            detail.ImporteCompensacionREAGYP),
                        })
            taxes = SIIReportLineTax.create(taxes_to_create)

            sii_report_line = {
                'report': self.id,
                'state': reg.EstadoFactura.EstadoRegistro,
                'last_modify_date': _datetime(
                    reg.EstadoFactura.TimestampUltimaModificacion),
                'communication_code': (
                    reg.EstadoFactura.CodigoErrorRegistro),
                'communication_msg': (
                    reg.EstadoFactura.DescripcionErrorRegistro),
                'issuer_vat_number': (
                    reg.IDFactura.IDEmisorFactura.NIF or
                    reg.IDFactura.IDEmisorFactura.IDOtro.ID),
                'serial_number': reg.IDFactura.NumSerieFacturaEmisor,
                'final_serial_number': (
                    reg.IDFactura.NumSerieFacturaEmisorResumenFin),
                'issue_date': invoice_date,
                'invoice_kind': reg.DatosFacturaRecibida.TipoFactura,
                'special_key': (reg.DatosFacturaRecibida.
                    ClaveRegimenEspecialOTrascendencia),
                'total_amount': _decimal(
                    reg.DatosFacturaRecibida.ImporteTotal),
                'taxes': [('add', [t.id for t in taxes])],
                'counterpart_name': (
                    reg.DatosFacturaRecibida.Contraparte.NombreRazon),
                'counterpart_id': (
                    reg.DatosFacturaRecibida.Contraparte.NIF or
                    reg.DatosFacturaRecibida.Contraparte.IDOtro.ID),
                'presenter': reg.DatosPresentacion.NIFPresentador,
                'presentation_date': _datetime(
                    reg.DatosPresentacion.TimestampPresentacion),
                'csv': reg.DatosPresentacion.CSV,
                'balance_state': reg.DatosPresentacion.CSV,
                'aeat_register': str(reg),
                }

            domain = [
                ('reference', '=', reg.IDFactura.NumSerieFacturaEmisor),
                ('invoice_date', '=', invoice_date),
                ('state', 'in', ('posted', 'paid')),
                ]
            vat = True
            if reg.IDFactura.IDEmisorFactura.NIF:
                vat = reg.IDFactura.IDEmisorFactura.NIF
                if not vat.startswith('ES'):
                    vat = 'ES' + vat
                domain.append(
                    ('party.tax_identifier', '=', vat)
                    )
            elif reg.IDFactura.IDEmisorFactura.IDOtro.IDType == '02':
                domain.append(
                    ('party.tax_identifier', '=',
                        reg.IDFactura.IDEmisorFactura.IDOtro.ID)
                    )
            else:
                vat = False
            invoices = Invoice.search(domain)
            if not vat and len(invoices) > 1:
                invoice_ok = []
                for invoice in invoices:
                    for register in registers:
                        if register == reg.IDFactura.IDEmisorFactura.IDOtro.ID:
                            invoice_ok.append(invoice)
                            break
                    invoices = invoice_ok
                    if invoice_ok:
                        break
            if invoices:
                sii_report_line['invoice'] = invoices[0].id
            lines_to_create.append(sii_report_line)
        SIIReportLine.create(lines_to_create)

        if pagination == 'S':
            self.query_recieved_invoices(last_invoice=last_invoice)


class SIIReportLine(ModelSQL, ModelView):
    '''
    AEAT SII Issued
    '''
    __name__ = 'aeat.sii.report.lines'

    report = fields.Many2One(
        'aeat.sii.report', 'Issued Report', ondelete='CASCADE')
    invoice = fields.Many2One('account.invoice', 'Invoice',
        states={
            'required': Eval('_parent_report', {}).get(
                'operation_type') != 'C0',
        })
    state = fields.Selection(AEAT_INVOICE_STATE, 'State')
    last_modify_date = fields.DateTime('Last Modification Date', readonly=True)
    communication_code = fields.Integer(
        'Communication Code', readonly=True)
    communication_msg = fields.Char(
        'Communication Message', readonly=True)
    company = fields.Many2One(
        'company.company', 'Company', required=True, select=True)
    issuer_vat_number = fields.Char('Issuer VAT Number', readonly=True)
    serial_number = fields.Char('Serial Number', readonly=True)
    final_serial_number = fields.Char('Final Serial Number', readonly=True)
    issue_date = fields.Date('Issued Date', readonly=True)
    invoice_kind = fields.Char('Invoice Kind', readonly=True)
    special_key = fields.Char('Special Key', readonly=True)
    total_amount = fields.Numeric('Total Amount', readonly=True)
    counterpart_name = fields.Char('Counterpart Name', readonly=True)
    counterpart_id = fields.Char('Counterpart ID', readonly=True)
    taxes = fields.One2Many(
        'aeat.sii.report.line.tax', 'line', 'Tax Lines', readonly=True)
    presenter = fields.Char('Presenter', readonly=True)
    presentation_date = fields.DateTime('Presentation Date', readonly=True)
    csv = fields.Char('CSV', readonly=True)
    balance_state = fields.Char('Balance State', readonly=True)
    # TODO counterpart balance data
    vat_code = fields.Function(fields.Char('VAT Code'), 'get_vat_code')
    identifier_type = fields.Function(
        fields.Selection(PARTY_IDENTIFIER_TYPE,
        'Identifier Type'), 'get_identifier_type')
    invoice_operation_key = fields.Function(
        fields.Selection(OPERATION_KEY, 'SII Operation Key'),
        'get_invoice_operation_key')
    exemption_cause = fields.Char('Exemption Cause', readonly=True)
    aeat_register = fields.Text('Register from AEAT Webservice', readonly=True)
    sii_header = fields.Text('Header')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        exist_sii_excemption_key = table.column_exist('exemption_key')
        if exist_sii_excemption_key:
            table.column_rename('exemption_key', 'exemption_cause')

        super(SIIReportLine, cls).__register__(module_name)

    def get_invoice_operation_key(self, name):
        return self.invoice.sii_operation_key if self.invoice else None

    def get_vat_code(self, name):
        if self.invoice and self.invoice.party_tax_identifier:
            return self.invoice.party_tax_identifier.code
        elif self.invoice and self.invoice.party.tax_identifier:
            return self.invoice.party.tax_identifier.code
        else:
            return None

    def get_identifier_type(self, name):
        return self.invoice.party.sii_identifier_type if self.invoice else None

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['state'] = None
        default['communication_code'] = None
        default['communication_msg'] = None
        default['issuer_vat_number'] = None
        default['serial_number'] = None
        default['final_serial_number'] = None
        default['issue_date'] = None
        default['invoice_kind'] = None
        default['special_key'] = None
        default['total_amount'] = None
        default['taxes'] = None
        default['counterpart_name'] = None
        default['counterpart_id'] = None
        default['presenter'] = None
        default['presentation_date'] = None
        default['csv'] = None
        default['balance_state'] = None
        return super(SIIReportLine, cls).copy(records, default=default)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        SIIReport = pool.get('aeat.sii.report')

        to_write = []
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            invoice = (Invoice(id=vals['invoice'])
                if vals.get('invoice') else None)
            report = (SIIReport(id=vals['report'])
                if vals.get('report') else None)

            delete = True if report and report.operation_type == 'D0' else False
            vals['sii_header'] = (str(invoice.get_sii_header(invoice, delete))
                if invoice else '')
            if vals.get('state', None) == 'Correcto' and invoice:
                to_write.extend(([invoice], {
                        'sii_pending_sending': False,
                        }))
        if to_write:
            Invoice.write(*to_write)
        return super(SIIReportLine, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        actions = iter(args)

        to_write = []
        for lines, values in zip(actions, actions):
            invoice_values = {
                'sii_pending_sending': False,
                }
            if values.get('state', None) == 'Correcto':
                invoices = [x.invoice for x in lines]
            else:
                invoices = [x.invoice for x in lines
                    if x.state == 'Correcto']
            if invoices:
                to_write.extend((invoices, invoice_values))

            invoice_vals = {
                'sii_pending_sending': False,
                'sii_state': 'duplicated_unsubscribed',
                }
            if values.get('communication_code', None) in (3000, 3001):
                invoices = [x.invoice for x in lines]
            else:
                invoices = [x.invoice for x in lines
                    if x.communication_code in (3000, 3001)]
            if invoices:
                to_write.extend((invoices, invoice_vals))

        super(SIIReportLine, cls).write(*args)
        if to_write:
            Invoice.write(*to_write)

    @classmethod
    def delete(cls, lines):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        to_save = []
        for line in lines:
            invoice = line.invoice
            if invoice:
                last_line = cls.search([
                        ('invoice', '=', invoice),
                        ('id', '!=', line.id),
                        ('report.operation_type', '!=', 'C0'),
                        ], order=[('report', 'DESC')], limit=1)
                last_line = last_line[0] if last_line else None
                if last_line:
                    invoice.sii_communication_type = (
                        last_line.report.operation_type)
                    invoice.sii_state = last_line.state
                    to_save.append(invoice)
                else:
                    invoice.sii_communication_type = None
                    invoice.sii_state = None
                    to_save.append(invoice)
        if to_save:
            Invoice.save(to_save)
        super(SIIReportLine, cls).delete(lines)


class SIIReportLineTax(ModelSQL, ModelView):
    '''
    SII Report Line Tax
    '''
    __name__ = 'aeat.sii.report.line.tax'

    line = fields.Many2One(
        'aeat.sii.report.lines', 'Report Line', ondelete='CASCADE')

    base = fields.Numeric('Base', readonly=True)
    rate = fields.Numeric('Rate', readonly=True)
    amount = fields.Numeric('Amount', readonly=True)
    surcharge_rate = fields.Numeric('Surcharge Rate', readonly=True)
    surcharge_amount = fields.Numeric('Surcharge Amount', readonly=True)
    reagyp_rate = fields.Numeric('REAGYP Rate', readonly=True)
    reagyp_amount = fields.Numeric('REAGYP Amount', readonly=True)


class CreateSiiIssuedPendingView(ModelView):
    """
    Create AEAT SII Issued Pending View
    """
    __name__ = "aeat.sii.issued.pending.view"


class CreateSiiIssuedPending(Wizard):
    """
    Create AEAT SII Issued Pending
    """
    __name__ = "aeat.sii.issued.pending"
    start_state = 'view'
    view = StateView('aeat.sii.issued.pending.view',
        'aeat_sii.aeat_sii_issued_pending_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('aeat_sii.act_aeat_sii_issued_report')

    def do_create_(self, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Report = pool.get('aeat.sii.report')

        reports = Report.search([
                ('state', 'in', ('draft', 'confirmed')),
                ('book', '=', 'E'),
                ])
        if reports:
            raise UserError(gettext('aeat_sii.reports_exist'))
        reports = Invoice.get_issued_sii_reports()
        reports = [x.id for x in reports] if reports else  []
        action['pyson_domain'] = PYSONEncoder().encode([
            ('id', 'in', reports),
            ])
        return action, {}


class CreateSiiReceivedPendingView(ModelView):
    """
    Create AEAT SII Received Pending View
    """
    __name__ = "aeat.sii.received.pending.view"


class CreateSiiReceivedPending(Wizard):
    """
    Create AEAT SII Received Pending
    """
    __name__ = "aeat.sii.received.pending"
    start_state = 'view'
    view = StateView('aeat.sii.received.pending.view',
        'aeat_sii.aeat_sii_received_pending_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateAction('aeat_sii.act_aeat_sii_received_report')


    def do_create_(self, action):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Report = pool.get('aeat.sii.report')

        reports = Report.search([
                ('state', 'in', ('draft', 'confirmed')),
                ('book', '=', 'R'),
                ])
        if reports:
            raise UserError(gettext('aeat_sii.reports_exist'))
        reports = Invoice.get_received_sii_reports()
        reports = [x.id for x in reports] if reports else []
        action['pyson_domain'] = PYSONEncoder().encode([
            ('id', 'in', reports),
            ])
        return action, {}
