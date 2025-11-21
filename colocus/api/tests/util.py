from pathlib import Path


def check_media_dir(d, test_module):
    if not isinstance(d, Path):
        d = Path(d)

    if not d.is_dir():
        raise Exception(f"Media directory does not exist or is not a directory: {d}")

    for p in test_module.__path__:
        p = Path(p)
        if str(d.relative_to(p)) == "media":
            return True

    return False
