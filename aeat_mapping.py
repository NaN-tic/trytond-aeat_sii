# -*- coding: utf-8 -*-
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from logging import getLogger
from operator import attrgetter
from datetime import date

from trytond.i18n import gettext
from trytond.model import Model
from trytond.pool import Pool
from trytond.exceptions import UserError
from . import tools


_logger = getLogger(__name__)

_DATE_FMT = '%d-%m-%Y'
_FIRST_SEMESTER_RECORD_DESCRIPTION = "Registro del Primer semestre"

RECTIFIED_KINDS = frozenset({'R1', 'R2', 'R3', 'R4', 'R5'})
OTHER_ID_TYPES = frozenset({'02', '03', '04', '05', '06', '07'})

SEMESTER1_ISSUED_SPECIALKEY = '16'
SEMESTER1_RECIEVED_SPECIALKEY = '14'


class BaseInvoiceMapper(Model):
    year = attrgetter('move.period.start_date.year')
    period = attrgetter('move.period.start_date.month')
    nif = attrgetter('company.party.sii_vat_code')
    issue_date = attrgetter('invoice_date')
    invoice_kind = attrgetter('sii_operation_key')
    rectified_invoice_kind = tools.fixed_value('I')

    def not_exempt_kind(self, tax):
        return attrgetter('sii_subjected_key')(tax)

    def exempt_kind(self, tax):
        return attrgetter('sii_exemption_cause')(tax)

    def not_subject(self, invoice):
        base = 0
        for line in invoice.lines:
            for tax in line.taxes:
                if (tax.sii_exemption_cause == 'NotSubject' and
                        not tax.service):
                    base += attrgetter('amount')(line)
        return base

    def counterpart_nif(self, invoice):
        nif = ''
        if invoice.sii_operation_key == 'F5':
            # Assume that the company party is configured correctly.
            nif = invoice.company.party.tax_identifier.code
        else:
            if invoice.party.tax_identifier:
                nif = invoice.party.tax_identifier.code
            elif invoice.party.identifiers:
                nif = invoice.party.identifiers[0].code
        if nif.startswith('ES'):
            nif = nif[2:]
        return nif

    def get_tax_amount(self, tax):
        val = attrgetter('company_amount')(tax)
        return val

    def get_tax_base(self, tax):
        val = attrgetter('company_base')(tax)
        return val

    def get_invoice_total(self, invoice):
        taxes = self.total_invoice_taxes(invoice)
        taxes_base = 0
        taxes_amount = 0
        taxes_surcharge = 0
        taxes_used = {}
        for tax in taxes:
            base = self.get_tax_base(tax)
            taxes_amount += self.get_tax_amount(tax)
            taxes_surcharge += self.tax_equivalence_surcharge_amount(tax) or 0
            parent = tax.tax.parent if tax.tax.parent else tax.tax
            if (parent.id in list(taxes_used.keys()) and
                    base == taxes_used[parent.id]):
                continue
            taxes_base += base
            taxes_used[parent.id] = base
        return (taxes_amount + taxes_base + taxes_surcharge)

    def counterpart_id_type(self, invoice):
        if invoice.sii_operation_key == 'F5':
            return invoice.company.party.sii_identifier_type
        else:
            if (invoice.sii_received_key == '09' and
                    invoice.party.sii_identifier_type != '02'):
                raise UserError(gettext('aeat_sii.msg_wrong_identifier_type',
                    invoice=invoice.number, party=invoice.party.rec_name))
            for tax in invoice.taxes:
                if (self.exempt_kind(tax.tax) == 'E5' and
                        invoice.party.sii_identifier_type != '02'):
                    raise UserError(gettext(
                            'aeat_sii.msg_wrong_identifier_type',
                            invoice=invoice.number,
                            party=invoice.party.rec_name))
            return invoice.party.sii_identifier_type

    counterpart_id = counterpart_nif
    total_amount = get_invoice_total
    tax_rate = attrgetter('tax.rate')
    tax_base = get_tax_base
    tax_amount = get_tax_amount

    def counterpart_name(self, invoice):
        if invoice.sii_operation_key == 'F5':
            return tools.unaccent(invoice.company.party.name)
        else:
            return tools.unaccent(invoice.party.name)

    def counterpart_country(self, invoice):
        return (invoice.invoice_address.country.code
            if invoice.invoice_address.country else '')

    def serial_number(self, invoice):
        return invoice.number if invoice.type == 'out' else invoice.reference

    def taxes(self, invoice):
        return [invoice_tax for invoice_tax in invoice.taxes if (
                invoice_tax.tax.tax_used and
                not invoice_tax.tax.recargo_equivalencia)]

    def total_invoice_taxes(self, invoice):
        return [invoice_tax for invoice_tax in invoice.taxes if (
                invoice_tax.tax.invoice_used and
                not invoice_tax.tax.recargo_equivalencia)]

    def _tax_equivalence_surcharge(self, invoice_tax):
        surcharge_tax = None
        for invoicetax in invoice_tax.invoice.taxes:
            if (invoicetax.tax.recargo_equivalencia and
                    invoice_tax.tax.recargo_equivalencia_related_tax ==
                    invoicetax.tax and invoicetax.base ==
                    invoicetax.base.copy_sign(invoice_tax.base)):
                surcharge_tax = invoicetax
                break
        return surcharge_tax

    def tax_equivalence_surcharge_rate(self, invoice_tax):
        surcharge_tax = self._tax_equivalence_surcharge(invoice_tax)
        if surcharge_tax:
            return self.tax_rate(surcharge_tax)

    def tax_equivalence_surcharge_amount(self, invoice_tax):
        surcharge_tax = self._tax_equivalence_surcharge(invoice_tax)
        if surcharge_tax:
            return self.tax_amount(surcharge_tax)

    def _build_period(self, invoice):
        return {
            'Ejercicio': self.year(invoice),
            'Periodo': tools._format_period(self.period(invoice)),
        }

    def _build_invoice_id(self, invoice):
        number = self.serial_number(invoice)
        ret = {
            'IDEmisorFactura': self._build_issuer_id(invoice),
            'NumSerieFacturaEmisor': number,
            'FechaExpedicionFacturaEmisor':
                self.issue_date(invoice).strftime(_DATE_FMT),
        }
        if self.invoice_kind(invoice) == 'F4':
            first_invoice = invoice.simplified_serial_number('first')
            last_invoice = invoice.simplified_serial_number('last')
            ret['NumSerieFacturaEmisor'] = number + first_invoice
            ret['NumSerieFacturaEmisorResumenFin'] = number + last_invoice
        return ret

    def _build_counterpart(self, invoice):
        ret = {
            'NombreRazon': self.counterpart_name(invoice),
        }
        id_type = self.counterpart_id_type(invoice)
        if id_type and id_type in OTHER_ID_TYPES:
            ret['IDOtro'] = {
                'IDType': id_type,
                'CodigoPais': self.counterpart_country(invoice),
                'ID': self.counterpart_id(invoice),
            }
        else:
            ret['NIF'] = self.counterpart_nif(invoice)
        return ret

    def _description(self, invoice):
        description = ''
        if invoice.description:
            description = tools.unaccent(invoice.description)
        if invoice.lines and invoice.lines[0].description:
            description = tools.unaccent(invoice.lines[0].description)
        description = self.serial_number(invoice)

        return (description if not self._is_first_semester(invoice)
            else _FIRST_SEMESTER_RECORD_DESCRIPTION
        )

    def build_query_filter(self, year=None, period=None, last_invoice=None):
        # TODO: IDFactura, Contraparte,
        # FechaPresentacion, FechaCuadre, FacturaModificada,
        # EstadoCuadre
        result = {
            'PeriodoLiquidacion': {
                'Ejercicio': year,
                'Periodo': tools._format_period(period),
                }
            }
        if last_invoice:
            result['ClavePaginacion'] = last_invoice
        return result


class IssuedInvoiceMapper(BaseInvoiceMapper):
    """
    Tryton Issued Invoice to AEAT mapper
    """
    __name__ = 'aeat.sii.issued.invoice.mapper'
    specialkey_or_trascendence = attrgetter('sii_issued_key')

    def _is_first_semester(self, invoice):
        return self.specialkey_or_trascendence(invoice) == \
            SEMESTER1_ISSUED_SPECIALKEY

    def build_delete_request(self, invoice):
        return {
            'PeriodoLiquidacion': self._build_period(invoice),
            'IDFactura': self._build_invoice_id(invoice),
        }

    def build_submit_request(self, invoice):
        request = self.build_delete_request(invoice)
        request['FacturaExpedida'] = self.build_issued_invoice(invoice)
        return request

    def _build_issuer_id(self, invoice):
        return {
            'NIF': self.nif(invoice),
        }

    def build_taxes(self, tax):
        res = {
            'TipoImpositivo': tools._rate_to_percent(self.tax_rate(tax)),
            'BaseImponible': self.tax_base(tax),
            'CuotaRepercutida': self.tax_amount(tax)
            }

        if self.tax_equivalence_surcharge_rate(tax):
            res['TipoRecargoEquivalencia'] = (
                tools._rate_to_percent(self.tax_equivalence_surcharge_rate(
                        tax)))

        if self.tax_equivalence_surcharge_amount(tax):
            res['CuotaRecargoEquivalencia'] = (
                self.tax_equivalence_surcharge_amount(tax))
        return res

    def location_rules(self, invoice):
        base = 0
        for line in invoice.lines:
            for tax in line.taxes:
                if (tax.sii_issued_key == '08' or
                        (tax.sii_exemption_cause == 'NotSubject' and
                            tax.service)):
                    base += attrgetter('amount')(line)
        return base

    def build_issued_invoice(self, invoice):
        ret = {
            'TipoFactura': self.invoice_kind(invoice),
            # TODO: FacturasAgrupadas
            # TODO: FacturasRectificadas
            # TODO: FechaOperacion
            'ClaveRegimenEspecialOTrascendencia':
                self.specialkey_or_trascendence(invoice),
            # TODO: ClaveRegimenEspecialOTrascendenciaAdicional1
            # TODO: ClaveRegimenEspecialOTrascendenciaAdicional2
            # TODO: NumRegistroAcuerdoFacturacion
            'ImporteTotal': self.total_amount(invoice),
            # TODO: BaseImponibleACoste
            'DescripcionOperacion': self._description(invoice),
            # TODO: RefExterna
            # TODO: FacturaSimplificadaArticulos7.2_7.3
            # TODO: EntidadSucedida
            # TODO: RegPrevioGGEEoREDEMEoCompetencia
            # TODO: Macrodato
            # TODO: DatosInmueble
            # TODO: ImporteTransmisionInmueblesSujetoAIVA
            # TODO: EmitidaPorTercerosODestinatario
            # TODO: FacturacionDispAdicinalTerceraYsextayDelMercadoOrganizadoDelGas
            # TODO: VariosDestinatarios
            # TODO: Cupon
            # TODO: FacturaSinIdentifDestinatarioArticulo6.1.d
            'TipoDesglose': {},
        }
        self._update_counterpart(ret, invoice)

        must_detail_op = (ret.get('Contraparte', {}) and (
            'IDOtro' in ret['Contraparte'] or ('NIF' in ret['Contraparte'] and
                ret['Contraparte']['NIF'].startswith('N')))
        )
        detail = {
            'Sujeta': {},
            'NoSujeta': {}
        }
        if must_detail_op:
            ret['TipoDesglose'].update({
                'DesgloseTipoOperacion': {
                    'Entrega': detail,
                    'PrestacionServicios': detail,
                }
            })
        else:
            ret['TipoDesglose'].update({
                'DesgloseFactura': detail
            })

        for tax in self.taxes(invoice):
            exempt_kind = self.exempt_kind(tax.tax)
            not_exempt_kind = self.not_exempt_kind(tax.tax)
            if (not_exempt_kind in ('S2', 'S3') and
                    'NIF' not in ret.get('Contraparte', {})):
                raise UserError(gettext('aeat_sii.msg_missing_nif',
                    invoice=invoice))

            if not_exempt_kind:
                if not_exempt_kind == 'S2':
                    # inv. subj. pass.
                    tax_detail = {
                        'TipoImpositivo': 0,
                        'BaseImponible': self.get_tax_base(tax),
                        'CuotaRepercutida': 0
                    }
                else:
                    tax_detail = self.build_taxes(tax)
                if tax_detail:
                    if (not detail['Sujeta'] or
                            not detail['Sujeta'].get('NoExenta')):
                        detail['Sujeta'].update({
                            'NoExenta': {
                                'TipoNoExenta': not_exempt_kind,
                                'DesgloseIVA': {
                                    'DetalleIVA': [tax_detail]
                                }
                            }
                        })
                    else:
                        detail['Sujeta']['NoExenta']['DesgloseIVA'][
                            'DetalleIVA'].append(tax_detail)
            elif exempt_kind:
                if exempt_kind != 'NotSubject':
                    baseimponible = self.get_tax_base(tax)
                    if detail['Sujeta'].get('Exenta', {}).get(
                            'DetalleExenta', {}).get(
                            'CausaExencion', None) == exempt_kind:
                        baseimponible += detail['Sujeta'].get('Exenta').get(
                            'DetalleExenta').get('BaseImponible', 0)
                    detail['Sujeta'].update({
                        'Exenta': {
                            'DetalleExenta': {
                                'CausaExencion': exempt_kind,
                                'BaseImponible': baseimponible,
                            }
                        }
                    })
        if self.not_subject(invoice):
            detail['NoSujeta'].update({
                    'ImportePorArticulos7_14_Otros': self.not_subject(
                        invoice),
                    })
        if self.location_rules(invoice):
            detail['NoSujeta'].update({
                    'ImporteTAIReglasLocalizacion': self.location_rules(
                        invoice)
                    })

        # remove unused key
        for key in ('Sujeta', 'NoSujeta'):
            if not detail[key]:
                detail.pop(key)

        if must_detail_op:
            if tax.tax.service:
                ret['TipoDesglose']['DesgloseTipoOperacion'].pop('Entrega')
            else:
                ret['TipoDesglose']['DesgloseTipoOperacion'].pop(
                    'PrestacionServicios')

        self._update_total_amount(ret, invoice)
        self._update_rectified_invoice(ret, invoice)
        return ret

    def _update_total_amount(self, ret, invoice):
        if (
            ret['TipoFactura'] == 'R5' and
            ret['TipoDesglose']['DesgloseFactura']['Sujeta'].get('NoExenta',
                None) and
            len(
                ret['TipoDesglose']['DesgloseFactura']['Sujeta']['NoExenta']
                ['DesgloseIVA']['DetalleIVA']
            ) == 1 and
            (
                ret['TipoDesglose']['DesgloseFactura']['Sujeta']['NoExenta']
                ['DesgloseIVA']['DetalleIVA'][0]['BaseImponible'] == 0
            )
        ):
            ret['ImporteTotal'] = self.total_amount(invoice)

    def _update_counterpart(self, ret, invoice):
        if ret['TipoFactura'] not in {'F2', 'F4', 'R5'}:
            ret['Contraparte'] = self._build_counterpart(invoice)

    def _update_rectified_invoice(self, ret, invoice):
        if ret['TipoFactura'] in RECTIFIED_KINDS:
            ret['TipoRectificativa'] = self.rectified_invoice_kind(invoice)
            if ret['TipoRectificativa'] == 'S':
                ret['ImporteRectificacion'] = {
                    'BaseRectificada': self.rectified_base(invoice),
                    'CuotaRectificada': self.rectified_amount(invoice),
                    # TODO: CuotaRecargoRectificado
                }


class RecievedInvoiceMapper(BaseInvoiceMapper):
    """
    Tryton Recieved Invoice to AEAT mapper
    """
    __name__ = 'aeat.sii.recieved.invoice.mapper'
    specialkey_or_trascendence = attrgetter('sii_received_key')
    move_date = attrgetter('move.date')

    def _is_first_semester(self, invoice):
        return self.specialkey_or_trascendence(invoice) == \
            SEMESTER1_RECIEVED_SPECIALKEY

    def _deductible_amount(self, invoice):
        val = Decimal(0)
        for tax in self.taxes(invoice):
            if tax.tax.deducible:
                val += tax.company_amount

        return val if not self._is_first_semester(invoice) else 0

    def _move_date(self, invoice):
        return (
            self.move_date(invoice)
            if not self._is_first_semester(invoice)
            else self.sent_date(invoice)
        )

    def sent_date(self, invoice):
        # Unless overriden, the date an invoice is sent to the SII system
        # is assumed to be the date it is being mapped
        return date.today()

    def build_delete_request(self, invoice):
        return {
            'PeriodoLiquidacion': self._build_period(invoice),
            'IDFactura': self._build_invoice_id(invoice),
        }

    def build_submit_request(self, invoice):
        request = self.build_delete_request(invoice)
        request['FacturaRecibida'] = self.build_received_invoice(invoice)
        return request

    _build_issuer_id = BaseInvoiceMapper._build_counterpart

    def build_received_invoice(self, invoice):
        ret = {
            'TipoFactura': self.invoice_kind(invoice),
            # TODO: FacturasAgrupadas: {IDFacturaAgrupada: [{Num, Fecha}]}
            # TODO: FechaOperacion
            'ClaveRegimenEspecialOTrascendencia':
                self.specialkey_or_trascendence(invoice),
            # TODO: ClaveRegimenEspecialOTrascendenciaAdicional1
            # TODO: ClaveRegimenEspecialOTrascendenciaAdicional2
            # TODO: NumRegistroAcuerdoFacturacion
            'ImporteTotal': self.total_amount(invoice),
            # TODO: BaseImponibleACoste
            'DescripcionOperacion': self._description(invoice),
            'DesgloseFactura': {},
            'Contraparte': self._build_counterpart(invoice),
            'FechaRegContable': self._move_date(invoice).strftime(_DATE_FMT),
            'CuotaDeducible': self._deductible_amount(invoice),
            # TODO: ADeducirEnPeriodoPosterior
            # TODO: EjercicioDeduccion
            # TODO: PeriodoDeduccion
        }
        _taxes = self.taxes(invoice)
        isp_taxes = self.isp_taxes(_taxes)
        _taxes = list(set(_taxes) - set(isp_taxes))
        if _taxes:
            ret['DesgloseFactura']['DesgloseIVA'] = {
                'DetalleIVA': [],
                }
        for tax in _taxes:
            validate_tax = self.build_taxes(invoice, tax)
            if validate_tax:
                ret['DesgloseFactura']['DesgloseIVA']['DetalleIVA'].append(
                    validate_tax)
        if isp_taxes:
            ret['DesgloseFactura']['InversionSujetoPasivo'] = {
                'DetalleIVA': []
                }
        for tax in isp_taxes:
            validate_tax = self.build_taxes(invoice, tax)
            if validate_tax:
                ret['DesgloseFactura']['InversionSujetoPasivo'][
                    'DetalleIVA'].append(validate_tax)
        self._update_rectified_invoice(ret, invoice)
        return ret

    def _update_rectified_invoice(self, ret, invoice):
        if ret['TipoFactura'] in RECTIFIED_KINDS:
            ret['TipoRectificativa'] = self.rectified_invoice_kind(invoice)
            # TODO: FacturasRectificadas:{IDFacturaRectificada:[{Num, Fecha}]}
            # TODO: ImporteRectificacion: {
            #   BaseRectificada, CuotaRectificada, CuotaRecargoRectificado }

    def build_taxes(self, invoice, tax):
        if tax.base is None and tax.amount is None:
            return
        ret = {
            'BaseImponible': self.tax_base(tax),
        }
        if self.specialkey_or_trascendence(invoice) != '02':
            ret['TipoImpositivo'] = tools._rate_to_percent(self.tax_rate(tax))
            ret['CuotaSoportada'] = self.tax_amount(tax)
            if self.tax_equivalence_surcharge_rate(tax):
                ret['TipoRecargoEquivalencia'] = \
                    tools._rate_to_percent(self.tax_equivalence_surcharge_rate(
                            tax))
            if self.tax_equivalence_surcharge_amount(tax):
                ret['CuotaRecargoEquivalencia'] = \
                    self.tax_equivalence_surcharge_amount(tax)
            bieninversion = all(map(lambda w: w in tax.tax.name, (
                        'bien', 'inversión')))
            ret['BienInversion'] = 'S' if bieninversion else 'N'
        else:
            ret['PorcentCompensacionREAGYP'] = \
                tools._rate_to_percent(self.tax_rate(tax))
            ret['ImporteCompensacionREAGYP'] = \
                (self.tax_amount(tax))
        return ret

    def isp_taxes(self, taxes):
        return [tax for tax in taxes if tax.tax.isp]
