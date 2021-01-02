from logging import getLogger
from requests import Session

from zeep import Client
from zeep.transports import Transport
from zeep.plugins import HistoryPlugin

from trytond.pool import Pool
from .tools import LoggingPlugin

_logger = getLogger(__name__)

wsdl_prod = ('https://www2.agenciatributaria.gob.es/static_files/common/'
    'internet/dep/aplicaciones/es/aeat/ssii_1_1_bis/fact/ws/')
wsdl_test = ('https://www6.aeat.es/static_files/common/internet/dep/'
    'aplicaciones/es/aeat/ssii_1_1_bis/fact/ws/')


def _get_client(wsdl, public_crt, private_key, test=False):
    session = Session()
    session.cert = (public_crt, private_key)
    transport = Transport(session=session)
    plugins = [HistoryPlugin()]
    # TODO: manually handle sessionId? Not mandatory yet recommended...
    # http://www.agenciatributaria.es/AEAT.internet/Inicio/Ayuda/Modelos__Procedimientos_y_Servicios/Ayuda_P_G417____IVA__Llevanza_de_libros_registro__SII_/Ayuda_tecnica/Informacion_tecnica_SII/Preguntas_tecnicas_frecuentes/1__Cuestiones_Generales/16___Como_se_debe_utilizar_el_dato_sesionId__.shtml
    if test:
        plugins.append(LoggingPlugin())
    client = Client(wsdl=wsdl, transport=transport, plugins=plugins)
    return client


def bind_issued_invoices_service(crt, pkey, test=False):
    wsdl = wsdl_prod + 'SuministroFactEmitidas.wsdl'
    port_name = 'SuministroFactEmitidas'
    if test:
        wsdl = wsdl_test + 'SuministroFactEmitidas.wsdl'
        port_name += 'Pruebas'

    cli = _get_client(wsdl, crt, pkey, test)

    return _IssuedInvoiceService(
        cli.bind('siiService', port_name))


def bind_recieved_invoices_service(crt, pkey, test=False):
    wsdl = wsdl_prod + 'SuministroFactRecibidas.wsdl'
    port_name = 'SuministroFactRecibidas'
    if test:
        wsdl = wsdl_test + 'SuministroFactRecibidas.wsdl'
        port_name += 'Pruebas'

    cli = _get_client(wsdl, crt, pkey, test)

    return _RecievedInvoiceService(
        cli.bind('siiService', port_name))


class _IssuedInvoiceService(object):
    def __init__(self, service):
        self.service = service

    def submit(self, headers, invoices):
        pool = Pool()
        IssuedMapper = pool.get('aeat.sii.issued.invoice.mapper')
        mapper = IssuedMapper()

        body = [mapper.build_submit_request(i) for i in invoices]
        _logger.debug(body)
        response_ = self.service.SuministroLRFacturasEmitidas(
            headers, body)
        _logger.debug(response_)
        return response_, str(body)

    def cancel(self, headers, body):
        _logger.debug(body)
        response_ = self.service.AnulacionLRFacturasEmitidas(
            headers, body)
        _logger.debug(response_)
        return response_

    def query(self, headers, year=None, period=None, last_invoice=None):
        pool = Pool()
        IssuedMapper = pool.get('aeat.sii.issued.invoice.mapper')
        mapper = IssuedMapper()

        filter_ = mapper.build_query_filter(year=year, period=period,
            last_invoice=last_invoice)
        _logger.debug(filter_)
        response_ = self.service.ConsultaLRFacturasEmitidas(
            headers, filter_)
        _logger.debug(response_)
        return response_


class _RecievedInvoiceService(object):
    def __init__(self, service):
        self.service = service

    def submit(self, headers, invoices):
        pool = Pool()
        ReceivedMapper = pool.get('aeat.sii.recieved.invoice.mapper')
        mapper = ReceivedMapper()

        body = [mapper.build_submit_request(i) for i in invoices]
        _logger.debug(body)
        response_ = self.service.SuministroLRFacturasRecibidas(
            headers, body)
        _logger.debug(response_)
        return response_, str(body)

    def cancel(self, headers, body):
        _logger.debug(body)
        response_ = self.service.AnulacionLRFacturasRecibidas(
            headers, body)
        _logger.debug(response_)
        return response_

    def query(self, headers, year=None, period=None, last_invoice=None):
        pool = Pool()
        ReceivedMapper = pool.get('aeat.sii.recieved.invoice.mapper')
        mapper = ReceivedMapper()

        filter_ = mapper.build_query_filter(year=year, period=period,
            last_invoice=last_invoice)
        _logger.debug(filter_)
        response_ = self.service.ConsultaLRFacturasRecibidas(
            headers, filter_)
        _logger.debug(response_)
        return response_
