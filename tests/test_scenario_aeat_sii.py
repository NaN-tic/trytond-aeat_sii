import datetime
import unittest
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from proteus import Model, Wizard
from trytond.exceptions import UserWarning
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear, create_tax,
                                                 create_tax_code, get_accounts)
from trytond.modules.account_invoice.tests.tools import \
    set_fiscalyear_invoice_sequences
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Imports
        today = datetime.date.today()

        # Install account_sii
        config = activate_modules('aeat_sii')

        # Create company
        _ = create_company()
        company = get_company()
        tax_identifier = company.party.identifiers.new()
        tax_identifier.type = 'eu_vat'
        tax_identifier.code = 'ES01234567L'
        company.party.save()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')
        Period = Model.get('account.period')
        period, = Period.find([
            ('start_date', '>=', today.replace(day=1)),
            ('end_date', '<=', today.replace(day=1) + relativedelta(months=+1)),
        ],
                              limit=1)

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create dummy certificate and add account configuration
        Certificate = Model.get('certificate')
        certificate = Certificate()
        certificate.name = 'Dummy'
        certificate.save()

        AccountConfiguration = Model.get('account.configuration')
        account_config = AccountConfiguration(1)
        account_config.aeat_certificate_sii = certificate
        account_config.save()

        # Create tax
        tax = create_tax(Decimal('.10'))
        tax.sii_book_key = 'E'
        tax.sii_issued_key = '01'
        tax.sii_subjected_key = 'S1'
        tax.tax_used = True
        tax.save()
        invoice_base_code = create_tax_code(tax, 'base', 'invoice')
        invoice_base_code.save()
        invoice_tax_code = create_tax_code(tax, 'tax', 'invoice')
        invoice_tax_code.save()
        credit_note_base_code = create_tax_code(tax, 'base', 'credit')
        credit_note_base_code.save()
        credit_note_tax_code = create_tax_code(tax, 'tax', 'credit')
        credit_note_tax_code.save()

        # Create party
        Party = Model.get('party.party')
        party = Party(name='Party')
        self.assertEqual(party.sii_identifier_type, 'SI')
        party.sii_identifier_type = None
        tax_identifier = party.identifiers.new()
        tax_identifier.type = 'eu_vat'
        tax_identifier.code = 'ES01234567L'
        party.save()

        self.assertEqual(party.sii_vat_code, '01234567L')

        # Create Simplified Invoice party
        simplified_party = Party(name='Party')
        simplified_party.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.customer_taxes.append(tax)
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        Product = Model.get('product.product')
        product = Product()
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'service'
        template.list_price = Decimal('40')
        template.cost_price = Decimal('25')
        template.account_category = account_category
        template.save()
        product, = template.products
        product.save()

        # Create payment term
        PaymentTerm = Model.get('account.invoice.payment_term')
        payment_term = PaymentTerm(name='Term')
        line = payment_term.lines.new(type='percent', ratio=Decimal('.5'))
        line.relativedeltas.new(days=20)
        line = payment_term.lines.new(type='remainder')
        line.relativedeltas.new(days=40)
        payment_term.save()

        # Create invoice
        Invoice = Model.get('account.invoice')
        InvoiceLine = Model.get('account.invoice.line')
        invoice = Invoice()
        invoice.party = party
        invoice.payment_term = payment_term
        line = InvoiceLine()
        invoice.lines.append(line)
        line.product = product
        line.quantity = 5
        line.unit_price = Decimal('40')
        line = InvoiceLine()
        invoice.lines.append(line)
        line.account = revenue
        line.description = 'Test'
        line.quantity = 1
        line.unit_price = Decimal(20)
        self.assertEqual(invoice.is_sii, True)
        invoice.save()
        self.assertEqual(invoice.is_sii, True)
        self.assertEqual(invoice.sii_book_key, 'E')
        self.assertEqual(invoice.sii_issued_key, '01')
        invoice.sii_book_key = 'I'
        invoice.sii_operation_key = 'F2'
        invoice.sii_issued_key = '02'
        invoice.save()
        invoice.reload()
        self.assertEqual(invoice.sii_book_key, 'I')
        reset_sii_keys = Wizard('aeat.sii.reset.keys', models=[invoice])
        reset_sii_keys.execute('reset')
        invoice.reload()
        self.assertEqual(invoice.sii_book_key, 'E')
        invoice.click('post')
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.sii_operation_key, 'F1')

        # Create Credit invoice
        invoice = Invoice()
        invoice.party = party
        invoice.payment_term = payment_term
        line = InvoiceLine()
        invoice.lines.append(line)
        line.product = product
        line.quantity = -5
        line.unit_price = Decimal('40')
        line = InvoiceLine()
        invoice.lines.append(line)
        line.account = revenue
        line.description = 'Test'
        line.quantity = -1
        line.unit_price = Decimal(20)
        invoice.sii_operation_key = 'R1'
        invoice.save()
        self.assertEqual(invoice.sii_book_key, 'E')
        self.assertEqual(invoice.sii_operation_key, 'R1')
        self.assertEqual(invoice.sii_issued_key, '01')
        invoice.sii_book_key = 'I'
        invoice.sii_operation_key = 'F2'
        invoice.sii_issued_key = '02'
        invoice.save()
        invoice.reload()
        reset_sii_keys = Wizard('aeat.sii.reset.keys', models=[invoice])
        reset_sii_keys.execute('reset')
        invoice.reload()
        self.assertEqual(invoice.sii_book_key, 'E')
        self.assertEqual(invoice.sii_operation_key, 'R1')
        invoice.click('post')
        self.assertEqual(invoice.state, 'posted')

        # Create AEAT Report
        AEATReport = Model.get('aeat.sii.report')
        report = AEATReport()
        report.fiscalyear = fiscalyear
        report.period = period
        report.operation_type = 'A0'
        report.book = 'E'
        report.save()
        self.assertEqual(report.state, 'draft')
        report.click('load_invoices')
        self.assertEqual(len(report.lines), 2)

        # Credit invoice with refund
        credit = Wizard('account.invoice.credit', [invoice])
        credit.form.with_refund = True
        credit.execute('credit')
        invoice.reload()
        self.assertEqual(invoice.state, 'cancelled')
        credit, = Invoice.find([('total_amount', '<', 0)])
        self.assertEqual(credit.sii_operation_key, 'R1')

        # Create simplified invoice
        Invoice = Model.get('account.invoice')
        InvoiceLine = Model.get('account.invoice.line')
        simplified_invoice = Invoice()
        simplified_invoice.party = simplified_party
        simplified_invoice.payment_term = payment_term
        line = InvoiceLine()
        simplified_invoice.lines.append(line)
        line.product = product
        line.quantity = 5
        line.unit_price = Decimal('40')
        line = InvoiceLine()
        simplified_invoice.lines.append(line)
        line.account = revenue
        line.description = 'Test'
        line.quantity = 1
        line.unit_price = Decimal(20)
        simplified_invoice.save()
        self.assertEqual(simplified_invoice.sii_book_key, 'E')
        self.assertEqual(simplified_invoice.sii_issued_key, '01')

        with self.assertRaises(UserWarning):
            try:
                simplified_invoice.click('post')
            except UserWarning as warning:
                _, (key, *_) = warning.args
                raise

        Warning = Model.get('res.user.warning')
        Warning.skip(key, True, config.context)
        simplified_invoice.click('post')
        self.assertEqual(simplified_invoice.state, 'posted')
        self.assertEqual(simplified_invoice.sii_operation_key, 'F2')
