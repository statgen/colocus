import logging
import os
import shutil
from subprocess import run

import pytest
from django.conf import settings

import colocus.tests
from colocus.api.tests.util import check_media_dir
from colocus.users.models import User
from colocus.users.tests.factories import UserFactory


@pytest.fixture(scope='session', autouse=True)
def django_logger():
    logger = logging.getLogger('django')
    return logger


@pytest.fixture(scope='session', autouse=True)
def django_db_setup(django_db_blocker, django_logger):
    # The database loading script will create some files the media directory, which we need to make sure have been
    # cleared out first
    if os.path.isdir(settings.MEDIA_ROOT):
        try:
            if check_media_dir(settings.MEDIA_ROOT, colocus.tests):
                django_logger.info("Clearing out test media directory...")
                django_logger.info(f"Media directory: {settings.MEDIA_ROOT}")
                shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        except Exception as e:
            django_logger.error(f"Media directory did not pass check, cannot delete, you may need to manually "
                                f"delete the directory before running tests: {settings.MEDIA_ROOT}")
            django_logger.error(f"Error was: {e}")
            raise e

    with django_db_blocker.unblock():
        # TODO: in the future, `load_dataset.py` should be converted into a django command
        # under colocus/api/management/commands/load_data.py
        print("Loading database for testing...")
        run(['python', 'manage.py', 'migrate'])
        # run(['python', 'scripts/load_dataset.py', 'colocus/tests/data/adipoexpress'])
        run(['python', 'scripts/load_dataset.py', 'colocus/tests/data/all-amp-datasets'])


@pytest.fixture
def user() -> User:
    return UserFactory()
