# -*- coding: utf-8 -*-
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from logging import getLogger
from operator import attrgetter

from pyAEATsii import mapping
from pyAEATsii import callback_utils

from trytond.model import Model
from trytond.pool import Pool
from . import tools

__all__ = [
    'IssuedTrytonInvoiceMapper',
    'RecievedTrytonInvoiceMapper',
    ]

_logger = getLogger(__name__)


class BaseTrytonInvoiceMapper(Model):

    def __init__(self, *args, **kwargs):
        super(BaseTrytonInvoiceMapper, self).__init__(*args, **kwargs)
        self.pool = Pool()

    year = attrgetter('move.period.fiscalyear.name')
    period = attrgetter('move.period.start_date.month')
    nif = attrgetter('company.party.sii_vat_code')
    issue_date = attrgetter('invoice_date')
    invoice_kind = attrgetter('sii_operation_key')
    rectified_invoice_kind = callback_utils.fixed_value('I')
    not_exempt_kind = attrgetter('sii_subjected_key')
    exempt_kind = attrgetter('sii_excemption_key')

    def counterpart_nif(self, invoice):
        if invoice.party.identifiers:
            nif = invoice.party.identifiers[0].code
            if nif.startswith('ES'):
                return nif[2:]
            return nif
        return ''

    counterpart_id_type = attrgetter('party.sii_identifier_type')
    counterpart_id = counterpart_nif
    untaxed_amount = attrgetter('untaxed_amount')
    total_amount = attrgetter('total_amount')
    tax_rate = attrgetter('tax.rate')
    tax_base = attrgetter('base')
    tax_amount = attrgetter('amount')

    def counterpart_name(self, invoice):
        return tools.unaccent(invoice.party.name)

    def description(self, invoice):
        if invoice.description:
            return tools.unaccent(invoice.description)
        if invoice.lines and invoice.lines[0].description:
            return tools.unaccent(invoice.lines[0].description)
        return self.serial_number(invoice)

    def counterpart_country(self, invoice):
        if invoice.party.sii_vat_country:
            return invoice.party.sii_vat_country
        return (invoice.invoice_address.country.code
            if invoice.invoice_address.country else '')

    def final_serial_number(self, invoice):
        try:
            SaleLine = self.pool.get('sale.line')
        except KeyError:
            SaleLine = None
        if SaleLine is not None:
            return max([
                line.origin.number
                for line in invoice.lines
                if isinstance(line.origin, SaleLine)
            ])

    def taxes(self, invoice):
        return [
            invoice_tax for invoice_tax in invoice.taxes
            if (
                invoice_tax.tax.sii_subjected_key == 'S1' and
                not invoice_tax.tax.recargo_equivalencia
            )
        ]

    def _tax_equivalence_surcharge(self, invoice_tax):
        parent_tax = invoice_tax.tax.parent
        if parent_tax:
            surcharge_taxes = [
                sibling
                for sibling in invoice_tax.invoice.taxes
                if (
                    sibling.tax.recargo_equivalencia and
                    sibling.tax.parent.id == parent_tax.id
                )
            ]
            if surcharge_taxes:
                (surcharge_tax,) = surcharge_taxes
                return surcharge_tax
        return None

    def tax_equivalence_surcharge_rate(self, invoice_tax):
        surcharge_tax = self._tax_equivalence_surcharge(invoice_tax)
        if surcharge_tax:
            return self.tax_rate(surcharge_tax)

    def tax_equivalence_surcharge_amount(self, invoice_tax):
        surcharge_tax = self._tax_equivalence_surcharge(invoice_tax)
        if surcharge_tax:
            return self.tax_amount(surcharge_tax)


class IssuedTrytonInvoiceMapper(mapping.IssuedInvoiceMapper,
        BaseTrytonInvoiceMapper):
    """
    Tryton Issued Invoice to AEAT mapper
    """
    __name__ = 'aeat.sii.issued.invoice.mapper'
    serial_number = attrgetter('number')
    specialkey_or_trascendence = attrgetter('sii_issued_key')


class RecievedTrytonInvoiceMapper(mapping.RecievedInvoiceMapper,
        BaseTrytonInvoiceMapper):
    """
    Tryton Recieved Invoice to AEAT mapper
    """
    __name__ = 'aeat.sii.recieved.invoice.mapper'
    serial_number = attrgetter('reference')
    specialkey_or_trascendence = attrgetter('sii_received_key')
    move_date = attrgetter('move.date')
    deductible_amount = attrgetter('tax_amount')  # most of the times
    tax_reagyp_rate = BaseTrytonInvoiceMapper.tax_rate
    tax_reagyp_amount = BaseTrytonInvoiceMapper.tax_amount
