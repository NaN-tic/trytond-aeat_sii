# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import invoice
from . import aeat
from . import party
from . import company
from . import load_pkcs12
from . import account
from . import aeat_mapping
from . import search_invoices


def register():
    Pool.register(
        account.TemplateTax,
        account.Tax,
        party.Party,
        company.Company,
        invoice.Invoice,
        invoice.Sale,
        invoice.Purchase,
        load_pkcs12.LoadPKCS12Start,
        aeat.SIIReport,
        aeat.SIIReportLine,
        aeat.SIIReportLineTax,
        aeat_mapping.IssuedTrytonInvoiceMapper,
        aeat_mapping.RecievedTrytonInvoiceMapper,
        search_invoices.StartView,
        module='aeat_sii', type_='model')
    Pool.register(
        load_pkcs12.LoadPKCS12,
        search_invoices.AddInvoicesWizard,
        module='aeat_sii', type_='wizard')
