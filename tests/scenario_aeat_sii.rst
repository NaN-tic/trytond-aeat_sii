=================
AEAT SII Scenario
=================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Install account_sii::

    >>> config = activate_modules('aeat_sii')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> Period = Model.get('account.period')
    >>> period, = Period.find([
    ...   ('start_date', '>=', today.replace(day=1)),
    ...   ('end_date', '<=', today.replace(day=1) + relativedelta(months=+1)),
    ...   ], limit=1)

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']

Create tax::

    >>> tax = set_tax_code(create_tax(Decimal('.10')))
    >>> tax.sii_book_key = 'E'
    >>> tax.sii_issued_key = '01'
    >>> tax.sii_subjected_key = 'S1'
    >>> tax.save()
    >>> invoice_base_code = tax.invoice_base_code
    >>> invoice_tax_code = tax.invoice_tax_code
    >>> credit_note_base_code = tax.credit_note_base_code
    >>> credit_note_tax_code = tax.credit_note_tax_code

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.cost_price = Decimal('25')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.customer_taxes.append(tax)
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> payment_term = PaymentTerm(name='Term')
    >>> line = payment_term.lines.new(type='percent', ratio=Decimal('.5'))
    >>> delta = line.relativedeltas.new(days=20)
    >>> line = payment_term.lines.new(type='remainder')
    >>> delta = line.relativedeltas.new(days=40)
    >>> payment_term.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> invoice.save()
    >>> invoice.sii_book_key
    u'E'
    >>> invoice.sii_operation_key
    u'F1'
    >>> invoice.sii_issued_key
    u'01'

    >>> invoice.sii_book_key = 'I'
    >>> invoice.sii_operation_key = 'F2'
    >>> invoice.sii_issued_key = '02'
    >>> invoice.save()
    >>> invoice.reload()

    >>> invoice.sii_book_key == 'I'
    True
    >>> invoice.click('reset_sii_keys')
    >>> invoice.reload()

    >>> invoice.sii_book_key == 'E'
    True
    >>> invoice.sii_operation_key == 'F1'
    True
    >>> invoice.click('post')
    >>> invoice.state
    u'posted'

Create Credit invoice::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.product = product
    >>> line.quantity = -5
    >>> line.unit_price = Decimal('40')
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = -1
    >>> line.unit_price = Decimal(20)
    >>> invoice.sii_operation_key = 'R1'
    >>> invoice.save()
    >>> invoice.sii_book_key
    u'E'
    >>> invoice.sii_operation_key
    u'R1'
    >>> invoice.sii_issued_key
    u'01'

    >>> invoice.sii_book_key = 'I'
    >>> invoice.sii_operation_key = 'F2'
    >>> invoice.sii_issued_key = '02'
    >>> invoice.save()
    >>> invoice.reload()
    >>> invoice.click('reset_sii_keys')
    >>> invoice.reload()

    >>> invoice.sii_book_key == 'E'
    True
    >>> invoice.sii_operation_key == 'R1'
    True
    >>> invoice.click('post')
    >>> invoice.state
    u'posted'

Create AEAT Report::

    >>> AEATReport = Model.get('aeat.sii.report')
    >>> report = AEATReport()
    >>> report.fiscalyear = fiscalyear
    >>> report.period = period
    >>> report.operation_type = 'A0'
    >>> report.book = 'E'
    >>> report.save()
    >>> report.state
    u'draft'
    >>> report.click('load_invoices')
    >>> len(report.lines)
    2


Credit invoice with refund::

    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = True
    >>> credit.execute('credit')
    >>> invoice.reload()
    >>> invoice.state
    'paid'
    >>> credit, = Invoice.find([('total_amount', '<', 0)])
    >>> credit.sii_operation_key
    'R1'
