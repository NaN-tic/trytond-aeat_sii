# -*- coding: utf-8 -*-
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unicodedata
from logging import getLogger
from decimal import Decimal
from datetime import datetime

from pyAEATsii import service
from pyAEATsii import mapping

from trytond.model import ModelSQL, ModelView, fields, Workflow
from trytond.pyson import Eval, Bool
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.config import config

__all__ = [
    'SIIReport',
    'SIIReportLine',
    'SIIReportLineTax',
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
    ('A0', 'Registration of invoices/records'),
    ('A1', 'Amendment of invoices/records (registration errors)'),
    # ('A4', 'Amendment of Invoice for Travellers'), # Not suported
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

OPERATION_KEY = [    # L2_EMI - L2_RECI
    (None, ''),
    ('F1', 'Invoice'),
    ('F2', 'Simplified Invoice (ticket)'),
    ('R1', 'Corrected Invoice (Art 80.1, 80.2 and 80.6 and error grounded in law)'),
    ('R2', 'Corrected Invoice (Art. 80.3)'),
    ('R3', 'Credit Note (Art 80.4)'),
    ('R4', 'Corrected Invoice (Other)'),
    ('R5', 'Corrected Invoice in simplified invoices'),
    ('F3', 'Invoice issued to replace simplified invoices issued and filed'),
    ('F4', 'Invoice summary entry'),
    ('F5', 'Import (DUA)'),
    ('F6', 'Other accounting documents'),

]

PARTY_IDENTIFIER_TYPE = [
    (None, ''),
    ('02', 'NIF-VAT'),
    ('03', 'Passport'),
    ('04', 'Official identification document issued by the country '
            'or region of residence'),
    ('05', 'Residence certificate'),
    ('06', 'Other supporting document'),
    ('07', 'Not registered'),
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
    ('16', 'First semester 2017'),
]

RECEIVE_SPECIAL_REGIME_KEY = [
    (None, ''),
    ('01', 'General tax regime activity'),
    ('02', 'Activities through which businesses pay compensation for special '
            'VAT arrangements for agriculture and fisheries'),
    ('03', 'Activities to which the special scheme of used goods, works of art, '
            'antiquities and collectables (135-139 of the VAT Law)'),
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
    ('14', 'First semester 2017'),
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
    ('Incorrecto', 'Rejected')
]


PROPERTY_STATE = [  # L6
    ('0', ''),
    ('1', '1. Property with a land register reference located in any part '
            'of Spain, with the exception of the Basque Country and Navarre'),
    ('2', '2. Property located in the Autonomous Community of the Basque '
            'Country or the Chartered Community of Navarre.'),
    ('3', '3. Property in any of the foregoing locations with no land register '
            'reference'),
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

# L9 - Excemption cause
EXCEMPTION_CAUSE = [
    (None, ''),
    ('E1', 'Exempt on account of Article 20'),
    ('E2', 'Exempt on account of Article 21'),
    ('E3', 'Exempt on account of Article 22'),
    ('E4', 'Exempt on account of Article 23 and Article 24'),
    ('E5', 'Exempt on account of Article 25'),
    ('E6', 'Exempt on other grounds'),
]

# L11 Payment Type
PAYMENT_TYPE = [
    ('01', 'Transfer'),
    ('02', 'Cheque'),
    ('03', 'Not to be collected/paid (deadline for accrual/forced accrual '
            'as part of insolvency proceedings)'),
    ('04', 'Other methods of collection/payment')
]

# L12
INTRACOMUNITARY_TYPE = [
    (None, ''),
    ('A', 'The transmission or receipt of goods to undertake partial reports '
            'or works stipulated in Article 70, section one, Number 7 '
            'of the Tax Law (Law 37/1992)'),
    ('B', 'Transfers of goods or intra-Community acquisitions of goods listed '
            'in Article 9.3 and Article 16.2 of the Tax Law (Law 37/1992)'),
]


def remove_accents(unicode_string):
    if isinstance(unicode_string, str):
        unicode_string_bak = unicode_string
        try:
            unicode_string = unicode_string_bak.decode('iso-8859-1')
        except UnicodeDecodeError:
            try:
                unicode_string = unicode_string_bak.decode('utf-8')
            except UnicodeDecodeError:
                return unicode_string_bak

    if not isinstance(unicode_string, unicode):
        return unicode_string

    # From http://www.leccionespracticas.com/uncategorized/eliminar-tildes-con-python-solucionado
    unicode_string_nfd = ''.join(
        (c for c in unicodedata.normalize('NFD', unicode_string)
            if (unicodedata.category(c) != 'Mn'
                or c in (u'\u0327', u'\u0303'))  # ç or ñ
            ))
    # It converts nfd to nfc to allow unicode.decode()
    return unicodedata.normalize('NFC', unicode_string_nfd)

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
    company_vat = fields.Char('VAT', size=9, states={
            'required': Eval('state').in_(['confirmed', 'done']),
            'readonly': ~Eval('state').in_(['draft', 'confirmed']),
        }, depends=['state'])
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
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
            ('sent', 'Sent'),
        ], 'State', readonly=True)
    communication_state = fields.Selection(AEAT_COMMUNICATION_STATE,
        'Communication State', readonly=True)
    csv = fields.Char('CSV', readonly=True)
    version = fields.Selection([
            ('0.7', '0.7'),
             ('1.0', '1.0'),
        ], 'Version', required=True,
        states={
            'readonly': Eval('state') != 'draft',
        },
        depends=['state'])
    lines = fields.One2Many('aeat.sii.report.lines', 'report',
        'Lines', states={
            'readonly':  Eval('state') != 'draft',
        }, depends=['state'])
    # TODO crash GTK client 4.x with widget date in XML view and attribute
    # readonly = True. At the moment, use PYSON to readonly field in XML views.
    send_date = fields.DateTime('Send date',
        states={
            'invisible': Eval('state') != 'sent',
            'readonly': Bool(Eval('state') == 'sent'),
        },
        depends=['state'])

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
                    }
                })
        cls._error_messages.update({
                'delete_cancel': ('Report "%s" must be cancelled before '
                    'deletion.'),
                })
        cls._transitions |= set((
                ('draft', 'confirmed'),
                ('draft', 'cancelled'),
                ('confirmed', 'draft'),
                ('confirmed', 'sent'),
                ('confirmed', 'cancelled'),
                ('cancelled', 'draft'),
                ))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company:
            return self.company.currency.id

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
        return '1.0'

    @fields.depends('company')
    def on_change_with_company_vat(self):
        if self.company:
            return self.company.party.sii_vat_code

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
                cls.raise_user_error('delete_cancel', (report.rec_name,))
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
        for report in reports:
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

        cls.write(reports, {
            'send_date': datetime.now()})
        _logger.debug('Done sending reports to AEAT SII')

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

            _logger.debug('Searching invoices for SII report: %s', domain)

            for invoice in Invoice.search(domain):
                to_create.append({
                    'report': report,
                    'invoice': invoice,
                })

        if to_create:
            ReportLine.create(to_create)

    def submit_issued_invoices(self):
        pool = Pool()
        mapper = pool.get('aeat.sii.issued.invoice.mapper')(pool=pool)

        _logger.info('Sending report %s to AEAT SII', self.id)
        headers = mapping.get_headers(
            name=self.company.party.name,
            vat=self.company_vat,
            comm_kind=self.operation_type,
            version=self.version)

        with self.company.tmp_ssl_credentials() as (crt, key):
            srv = service.bind_issued_invoices_service(
                crt, key, test=SII_TEST)
            try:
                res = srv.submit(
                    headers, (line.invoice for line in self.lines),
                    mapper=mapper)
            except Exception as e:
                self.raise_user_error(str(e))

        self._save_response(res)

    def delete_issued_invoices(self):
        pool = Pool()
        mapper = pool.get('aeat.sii.issued.invoice.mapper')(pool=pool)

        headers = mapping.get_headers(
            name=self.company.party.name,
            vat=self.company_vat,
            comm_kind=self.operation_type,
            version=self.version)

        with self.company.tmp_ssl_credentials() as (crt, key):
            srv = service.bind_issued_invoices_service(
                crt, key, test=SII_TEST)
            try:
                res = srv.cancel(
                    headers, (line.invoice for line in self.lines),
                    mapper=mapper)
            except Exception as e:
                self.raise_user_error(str(e))

        self._save_response(res)

    def query_issued_invoices(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        headers = mapping.get_headers(
            name=self.company.party.name,
            vat=self.company_vat,
            comm_kind=self.operation_type,
            version=self.version)

        with self.company.tmp_ssl_credentials() as (crt, key):
            srv = service.bind_issued_invoices_service(
                crt, key, test=SII_TEST)
            res = srv.query(
                headers,
                year=self.fiscalyear.name,
                period=self.period.start_date.month)

        registers = \
            res.RegistroRespuestaConsultaLRFacturasEmitidas
        # FIXME: the number can be repeated over time
        invoices_list = Invoice.search([
            ('number', 'in', [
                reg.IDFactura.NumSerieFacturaEmisor
                for reg in registers
            ])
        ])
        invoices_ids = {
            invoice.number: invoice.id
            for invoice in invoices_list
        }
        self.lines = tuple(
            SIIReportLine(
                invoice=invoices_ids.get(reg.IDFactura.NumSerieFacturaEmisor),
                state=reg.EstadoFactura.EstadoRegistro,
                communication_code=reg.EstadoFactura.CodigoErrorRegistro,
                communication_msg=reg.EstadoFactura.DescripcionErrorRegistro,
                issuer_vat_number=(
                    reg.IDFactura.IDEmisorFactura.NIF or
                    reg.IDFactura.IDEmisorFactura.IDOtro.ID),
                serial_number=reg.IDFactura.NumSerieFacturaEmisor,
                final_serial_number=(
                    reg.IDFactura.NumSerieFacturaEmisorResumenFin),
                issue_date=_date(
                    reg.IDFactura.FechaExpedicionFacturaEmisor),
                invoice_kind=reg.DatosFacturaEmitida.TipoFactura,
                special_key=(
                    reg.DatosFacturaEmitida.
                    ClaveRegimenEspecialOTrascendencia),
                total_amount=_decimal(reg.DatosFacturaEmitida.ImporteTotal),
                taxes=tuple(
                    SIIReportLineTax(
                        base=_decimal(detail.BaseImponible),
                        rate=_decimal(detail.TipoImpositivo),
                        amount=_decimal(detail.CuotaRepercutida),
                        surcharge_rate=_decimal(detail.TipoRecargoEquivalencia),
                        surcharge_amount=_decimal(detail.CuotaRecargoEquivalencia),
                    )
                    for detail in reg.DatosFacturaEmitida.TipoDesglose.
                    DesgloseFactura.Sujeta.NoExenta.DesgloseIVA.DetalleIVA
                ),
                counterpart_name=(
                    reg.DatosFacturaEmitida.Contraparte.NombreRazon
                    if reg.DatosFacturaEmitida.Contraparte else None),
                counterpart_id=(
                    (
                        reg.DatosFacturaEmitida.Contraparte.NIF or
                        reg.DatosFacturaEmitida.Contraparte.IDOtro.ID)
                    if reg.DatosFacturaEmitida.Contraparte else None),
                presenter=reg.DatosPresentacion.NIFPresentador,
                presentation_date=_datetime(
                    reg.DatosPresentacion.TimestampPresentacion),
                csv=reg.DatosPresentacion.CSV,
                balance_state=reg.DatosPresentacion.CSV,
            )
            for reg in registers
        )
        self.save()

    def submit_recieved_invoices(self):
        pool = Pool()
        mapper = pool.get('aeat.sii.recieved.invoice.mapper')(pool=pool)

        _logger.info('Sending report %s to AEAT SII', self.id)
        headers = mapping.get_headers(
            name=self.company.party.name,
            vat=self.company_vat,
            comm_kind=self.operation_type,
            version=self.version)

        with self.company.tmp_ssl_credentials() as (crt, key):
            srv = service.bind_recieved_invoices_service(
                crt, key, test=SII_TEST)
            try:
                res = srv.submit(
                    headers, (line.invoice for line in self.lines),
                    mapper=mapper)
            except Exception as e:
                self.raise_user_error(str(e))

        self._save_response(res)

    def delete_recieved_invoices(self):
        pool = Pool()
        mapper = pool.get('aeat.sii.recieved.invoice.mapper')(pool=pool)

        headers = mapping.get_headers(
            name=self.company.party.name,
            vat=self.company_vat,
            comm_kind=self.operation_type,
            version=self.version)

        with self.company.tmp_ssl_credentials() as (crt, key):
            srv = service.bind_recieved_invoices_service(
                crt, key, test=SII_TEST)
            try:
                res = srv.cancel(
                    headers, (line.invoice for line in self.lines),
                    mapper=mapper)
            except Exception as e:
                self.raise_user_error(str(e))

        self._save_response(res)

    def _save_response(self, response):
        for (report_line, response_line) in zip(
                self.lines, response.RespuestaLinea):
            report_line.state = response_line.EstadoRegistro
            report_line.communication_code = response_line.CodigoErrorRegistro
            report_line.communication_msg = (
                response_line.DescripcionErrorRegistro)
            report_line.save()
        self.communication_state = response.EstadoEnvio
        self.csv = response.CSV
        self.save()

    def query_recieved_invoices(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        SIIReportLine = pool.get('aeat.sii.report.lines')
        SIIReportLineTax = pool.get('aeat.sii.report.line.tax')

        headers = mapping.get_headers(
            name=self.company.party.name,
            vat=self.company_vat,
            comm_kind=self.operation_type,
            version=self.version)

        with self.company.tmp_ssl_credentials() as (crt, key):
            srv = service.bind_recieved_invoices_service(
                crt, key, test=SII_TEST)
            res = srv.query(
                headers,
                year=self.fiscalyear.name,
                period=self.period.start_date.month)

        _logger.debug(res)
        registers = res.RegistroRespuestaConsultaLRFacturasRecibidas

        # FIXME: the reference is not forced to be unique
        invoices_list = Invoice.search([
            ('reference', 'in', [
                reg.IDFactura.NumSerieFacturaEmisor
                for reg in registers
            ])
        ])
        invoices_ids = {
            invoice.reference: invoice.id
            for invoice in invoices_list
        }
        self.lines = tuple(
            SIIReportLine(
                invoice=invoices_ids.get(reg.IDFactura.NumSerieFacturaEmisor),
                state=reg.EstadoFactura.EstadoRegistro,
                communication_code=reg.EstadoFactura.CodigoErrorRegistro,
                communication_msg=reg.EstadoFactura.DescripcionErrorRegistro,
                issuer_vat_number=(
                    reg.IDFactura.IDEmisorFactura.NIF or
                    reg.IDFactura.IDEmisorFactura.IDOtro.ID),
                serial_number=reg.IDFactura.NumSerieFacturaEmisor,
                final_serial_number=(
                    reg.IDFactura.NumSerieFacturaEmisorResumenFin),
                issue_date=_date(
                    reg.IDFactura.FechaExpedicionFacturaEmisor),
                invoice_kind=reg.DatosFacturaRecibida.TipoFactura,
                special_key=(
                    reg.DatosFacturaRecibida.
                    ClaveRegimenEspecialOTrascendencia),
                total_amount=_decimal(reg.DatosFacturaRecibida.ImporteTotal),
                taxes=tuple(
                    SIIReportLineTax(
                        base=_decimal(detail.BaseImponible),
                        rate=_decimal(detail.TipoImpositivo),
                        amount=_decimal(detail.CuotaSoportada),
                        surcharge_rate=_decimal(detail.TipoRecargoEquivalencia),
                        surcharge_amount=_decimal(detail.CuotaRecargoEquivalencia),
                        reagyp_rate=_decimal(detail.PorcentCompensacionREAGYP),
                        reagyp_amount=_decimal(detail.ImporteCompensacionREAGYP),
                    )
                    for detail in reg.DatosFacturaRecibida.
                    DesgloseFactura.DesgloseIVA.DetalleIVA
                ),
                counterpart_name=(
                    reg.DatosFacturaRecibida.Contraparte.NombreRazon),
                counterpart_id=(
                    reg.DatosFacturaRecibida.Contraparte.NIF or
                    reg.DatosFacturaRecibida.Contraparte.IDOtro.ID),
                presenter=reg.DatosPresentacion.NIFPresentador,
                presentation_date=_datetime(
                    reg.DatosPresentacion.TimestampPresentacion),
                csv=reg.DatosPresentacion.CSV,
                balance_state=reg.DatosPresentacion.CSV,
            )
            for reg in registers
        )
        self.save()


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

    def get_invoice_operation_key(self, name):
        return self.invoice.sii_operation_key

    def get_vat_code(self, name):
        return self.invoice.party.vat_code if self.invoice else None

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
