# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import cron
from . import invoice
from . import aeat
from . import party
from . import account
from . import aeat_mapping
from . import sale
from . import purchase
from . import contract


def register():
    Pool.register(
        account.Configuration,
        account.ConfigurationDefaultSII,
        account.TemplateTax,
        account.Tax,
        cron.Cron,
        party.Party,
        party.PartyIdentifier,
        invoice.Invoice,
        invoice.ResetSIIKeysStart,
        invoice.ResetSIIKeysEnd,
        invoice.InvoiceLine,
        aeat.CreateSiiIssuedPendingView,
        aeat.CreateSiiReceivedPendingView,
        aeat.SIIReport,
        aeat.SIIReportLine,
        aeat.SIIReportLineTax,
        aeat_mapping.IssuedInvoiceMapper,
        aeat_mapping.RecievedInvoiceMapper,
        module='aeat_sii', type_='model')
    Pool.register(
        contract.ContractConsumption,
        depends=['contract'],
        module='aeat_sii', type_='model')
    Pool.register(
        sale.Sale,
        depends=['sale'],
        module='aeat_sii', type_='model')
    Pool.register(
        purchase.Purchase,
        depends=['purchase'],
        module='aeat_sii', type_='model')
    Pool.register(
        invoice.ResetSIIKeys,
        aeat.CreateSiiIssuedPending,
        aeat.CreateSiiReceivedPending,
        module='aeat_sii', type_='wizard')
