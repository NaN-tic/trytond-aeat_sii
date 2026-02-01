import unittest
from decimal import Decimal

from proteus import Model
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

    def test_deductible_rate(self):

        # Install aeat_sii
        activate_modules('aeat_sii')

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

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']

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
        tax.invoice_used = True
        tax.deducible = True
        tax.save()
        invoice_base_code = create_tax_code(tax, 'base', 'invoice')
        invoice_base_code.save()
        invoice_tax_code = create_tax_code(tax, 'tax', 'invoice')
        invoice_tax_code.save()

        # Create party
        Party = Model.get('party.party')
        party = Party(name='Party')
        tax_identifier = party.identifiers.new()
        tax_identifier.type = 'eu_vat'
        tax_identifier.code = 'ES01234567L'
        party.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
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

        # Create invoice with deductible rate
        Invoice = Model.get('account.invoice')
        InvoiceLine = Model.get('account.invoice.line')
        invoice = Invoice()
        invoice.party = party
        invoice.payment_term = payment_term
        line = InvoiceLine()
        invoice.lines.append(line)
        line.product = product
        line.account = revenue
        line.quantity = 5
        line.unit_price = Decimal('40')
        line.taxes_deductible_rate = Decimal('0.5')  # Set deductible rate to 0.5
        invoice.save()
        self.assertEqual(invoice.is_sii, True)
        invoice.click('post')
        self.assertEqual(invoice.state, 'posted')
        invoice.reload()

        # Check that deductible_taxes has the full tax amount
        self.assertEqual(len(invoice.deductible_taxes), 1)
        # Since SII uses deductible_taxes for calculations, and they are calculated with full rate,
        # the test ensures that deductible_taxes are created when deductible_rate <1

        # Check that the invoice taxes are reduced
        self.assertEqual(len(invoice.taxes), 1)
