# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from io import BytesIO
from logging import getLogger

from OpenSSL.crypto import load_pkcs12
from OpenSSL.crypto import dump_certificate
from OpenSSL.crypto import dump_privatekey
from OpenSSL.crypto import FILETYPE_PEM
from OpenSSL.crypto import Error as CryptoError

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import ModelView
from trytond.model import fields
from trytond.wizard import Wizard
from trytond.wizard import StateView
from trytond.wizard import StateTransition
from trytond.wizard import Button
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = [
    'LoadPKCS12',
    'LoadPKCS12Start',
]
_logger = getLogger(__name__)


class LoadPKCS12Start(ModelView):
    "Load PKCS12 Start"
    __name__ = "aeat.sii.load_pkcs12.start"

    pfx = fields.Binary('PFX File', required=True)
    password = fields.Char('Password', required=True)


class LoadPKCS12(Wizard):
    "Load PKCS12"
    __name__ = "aeat.sii.load_pkcs12"
    start = StateView(
        'aeat.sii.load_pkcs12.start',
        'aeat_sii.load_pkcs12_start_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Load', 'load', 'tryton-ok', default=True),
        ])
    load = StateTransition()

    def transition_load(self):
        Company = Pool().get('company.company')
        company_id = Transaction().context['active_id']
        (company,) = Company.browse([company_id])
        with BytesIO(self.start.pfx) as pfx:
            try:
                pkcs12 = load_pkcs12(pfx.read(), self.start.password)
                crt = dump_certificate(FILETYPE_PEM, pkcs12.get_certificate())
                key = dump_privatekey(FILETYPE_PEM, pkcs12.get_privatekey())
                Company.write([company], {
                    'pem_certificate': crt,
                    'private_key': key,
                })
                _logger.info(
                    'Correctly loaded SSL credentials for company %s',
                    company.rec_name)
            except CryptoError as e:
                _logger.debug('Cryptographic error loading pkcs12 %s', e)
                errors = e.args[0]
                message = ', '.join(error[2] for error in errors)
                raise UserError(gettext('aeat_sii.error_loading_pkcs12',
                    message=message))
        return 'end'
