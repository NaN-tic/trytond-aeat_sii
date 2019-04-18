# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from logging import getLogger
from contextlib import contextmanager
from tempfile import NamedTemporaryFile

from cryptography.fernet import Fernet

from trytond.config import config
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['Company']
_logger = getLogger(__name__)


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    pem_certificate = fields.Binary('PEM Certificate')
    encrypted_private_key = fields.Binary('Encrypted Private Key')
    private_key = fields.Function(fields.Binary('Private Key'),
        'get_private_key', 'set_private_key')

    @classmethod
    def get_private_key(cls, companies, name=None):
        converter = bytes
        default = None
        format_ = Transaction().context.pop(
            '%s.%s' % (cls.__name__, name), '')
        if format_ == 'size':
            converter = len
            default = 0

        pkeys = []
        for company in companies:
            key = company._get_private_key(name)
            if not key:
                continue
            pkeys.append(key)

        if not pkeys:
            return {company.id:None for x in companies}

        return {
            company.id: converter(pkey) if pkey else default
            for (company, pkey) in zip(companies, pkeys)
        }

    def _get_private_key(self, name=None):
        if not self.encrypted_private_key:
            return None
        fernet = self.get_fernet_key()
        if not fernet:
            return None
        decrypted_key = fernet.decrypt(bytes(self.encrypted_private_key))
        return decrypted_key

    @classmethod
    def set_private_key(cls, companies, name, value):
        encrypted_key = None
        if value:
            fernet = cls.get_fernet_key()
            encrypted_key = fernet.encrypt(bytes(value))
        cls.write(companies, {'encrypted_private_key': encrypted_key})

    @classmethod
    def get_fernet_key(cls):
        fernet_key = config.get('cryptography', 'fernet_key')
        if not fernet_key:
            _logger.error('Missing Fernet key configuration')
            # raise UserError(gettext('aeat_sii.msg_missing_fernet_key'))
        else:
            return Fernet(fernet_key)

    @contextmanager
    def tmp_ssl_credentials(self):
        if not self.pem_certificate:
            raise UserError(gettext('aeat_sii.msg_missing_pem_cert'))
        with NamedTemporaryFile(suffix='.crt') as crt:
            with NamedTemporaryFile(suffix='.pem') as key:
                crt.write(self.pem_certificate)
                key.write(self.private_key)
                crt.flush()
                key.flush()
                yield (crt.name, key.name)
