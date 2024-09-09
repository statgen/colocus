import re
from pathlib import Path

REGEX_MARKER = re.compile(r'^(?:chr)?([a-zA-Z0-9]+?)[_:-](\d+)[_:|-]?([A-Za-z]+)?[/_:|-]?([^_]+)?_?(.*)?')


def parse_variant(v):
    m = REGEX_MARKER.search(v)
    if m:
        return m.groups()
    else:
        return None


def is_variant(v):
    return parse_variant(v) is not None


def valid_alleles(s):
    for a in s:
        if a not in "ACGTN":
            return False
    return True


def check_media_dir(d, test_module):
    if not isinstance(d, Path):
        d = Path(d)

    if not d.is_dir():
        raise Exception(f'Media directory does not exist or is not a directory: {d}')

    for p in test_module.__path__:
        p = Path(p)
        if str(d.relative_to(p)) == 'media':
            return True

    return False
