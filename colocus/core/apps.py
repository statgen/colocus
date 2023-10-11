import sys, platform
from pathlib import Path

from django.apps import AppConfig
from django.db.backends.signals import connection_created

ROOT_DIR = Path(__file__).resolve(strict=True).parent.parent.parent


def load_uint(connection, **kwargs):
    if connection.vendor != 'sqlite':
        return

    connection.connection.enable_load_extension(True)

    if sys.platform == 'darwin':
        if platform.machine() == "arm64":
            ext_path = ROOT_DIR / "sqlite3" / "uint" / "arm64" / "uint.dylib"
        elif platform.machine() == "x86_64":
            ext_path = ROOT_DIR / "sqlite3" / "uint" / "x86_64" / "uint.dylib"
        else:
            raise NotImplementedError(f"Unsupported Mac CPU architecture: {platform.machine()}")
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
