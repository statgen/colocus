import re

REGEX_MARKER = re.compile(
    r"^(?:chr)?([a-zA-Z0-9]+?)[_:-](\d+)[_:|-]?([A-Za-z]+)?[/_:|-]?([^_]+)?_?(.*)?"
)


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
