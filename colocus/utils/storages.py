from django.core.files.storage import get_storage_class


class OverwriteStorage(get_storage_class()):
    """
    By default, django saves new `FileField` files by appending a unique ID after the provided filename.
        (if a file is replaced, a new copy is saved; the file is not overwritten)

    This is not so convenient for tabix, and could also end up with dangling copies of big files unexpectedly.

    To use, each individual filefield must manually specify `FileField(*, storage=OverwriteStorage())`
    """
    def _save(self, name, content):
        # There is a theoretical race condition if the same file was uploaded twice at same time, but our ingest
        #   process is based solely on batch mode.
        self.delete(name)
        return super(OverwriteStorage, self)._save(name, content)

    def get_available_name(self, name, max_length=None):
        return name

# from storages.backends.s3boto3 import S3Boto3Storage
#
#
# class StaticRootS3Boto3Storage(S3Boto3Storage):
#     location = "static"
#     default_acl = "public-read"
#
#
# class MediaRootS3Boto3Storage(S3Boto3Storage):
#     location = "media"
#     file_overwrite = False
