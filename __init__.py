# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool

from . import invoice
from . import aeat
from . import party
from . import company
from . import load_pkcs12
from . import account


def register():
    Pool.register(
        account.TemplateTax,
        account.Tax,
        party.Party,
        company.Company,
        invoice.Invoice,
        load_pkcs12.LoadPKCS12Start,
        aeat.SIIReport,
        aeat.SIIReportLine,
        aeat.IssuedTrytonInvoiceMapper,
        aeat.RecievedTrytonInvoiceMapper,
        module='aeat_sii', type_='model')
    Pool.register(
        load_pkcs12.LoadPKCS12,
        module='aeat_sii', type_='wizard')
