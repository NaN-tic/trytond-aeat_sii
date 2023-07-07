=================
Invoice in Future
=================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (create_company,
    ...     get_company)
    >>> from trytond.modules.account.tests.tools import (create_fiscalyear,
    ...     create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('aeat_sii')

Create company::

    >>> _ = create_company()
    >>> company = get_company()
    >>> tax_identifier = company.party.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'ES01234567L'
    >>> company.party.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> expense = accounts['expense']
    >>> revenue = accounts['revenue']

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.sii_identifier_type
    'SI'
    >>> party.sii_identifier_type = None
    >>> tax_identifier = company.party.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'ES01234567L'
    >>> party.save()

Create IN invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice_in = Invoice()
    >>> invoice_in.type = 'in'
    >>> invoice_in.party = party
    >>> invoice_in.invoice_date = today
    >>> line = invoice_in.lines.new()
    >>> line.account = expense
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)

Posting IN invoice without reference raises a warning::

    >>> invoice_in.click('post')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserWarning: ...

Create OUT invoice::

    >>> invoice_out = Invoice()
    >>> invoice_out.type = 'out'
    >>> invoice_out.party = party
    >>> invoice_out.invoice_date = today
    >>> line = invoice_out.lines.new()
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)

Post OUT invoice::

    >>> invoice_out.click('post')
    >>> invoice_out.state
    'posted'
