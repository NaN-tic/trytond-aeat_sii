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
from . import sale
from . import purchase


def register():
    Pool.register(
        account.TemplateTax,
        account.Tax,
        party.Party,
        party.PartyIdentifier,
        company.Company,
        invoice.Invoice,
        load_pkcs12.LoadPKCS12Start,
        aeat.CreateSiiIssuedPendingView,
        aeat.CreateSiiReceivedPendingView,
        aeat.SIIReport,
        aeat.SIIReportLine,
        aeat.SIIReportLineTax,
        aeat_mapping.IssuedTrytonInvoiceMapper,
        aeat_mapping.RecievedTrytonInvoiceMapper,
        sale.Sale,
        module='aeat_sii', type_='model')
    Pool.register(
        purchase.Purchase,
        depends=['purchase'],
        module='aeat_sii', type_='model')
    Pool.register(
        aeat.CreateSiiIssuedPending,
        aeat.CreateSiiReceivedPending,
        load_pkcs12.LoadPKCS12,
        module='aeat_sii', type_='wizard')
