import sys
from pathlib import Path

from django.apps import AppConfig
from django.db.backends.signals import connection_created

ROOT_DIR = Path(__file__).resolve(strict=True).parent.parent.parent


def load_uint(connection, **kwargs):
    if connection.vendor != 'sqlite':
        return

    connection.connection.enable_load_extension(True)

    if sys.platform == 'darwin':
        ext_path = ROOT_DIR / "sqlite3" / "uint" / "uint.dylib"
    elif sys.platform == 'linux':
        ext_path = ROOT_DIR / "sqlite3" / "uint" / "uint.so"
    else:
        raise NotImplementedError(f"Unsupported platform: {sys.platform}")

    connection.connection.load_extension(str(ext_path))


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'colocus.core'

    def ready(self):
        connection_created.connect(load_uint)
