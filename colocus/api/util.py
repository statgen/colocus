import dataclasses
import math
import typing as ty

from zorp.parsers import BasicVariant

@dataclasses.dataclass
class MergedVariant:
    """The merged results of data for two aligned iterators, like marginal / conditional or trait1 / trait2"""
    # Same variant = same spec by definition
    chrom: str
    pos: int
    ref: str
    alt: str

    # Dataset / trait 1
    t1_neg_log_pvalue: float
    t1_beta: float
    t1_stderr_beta: float
    t1_alt_allele_freq: float

    # Dataset / trait 2
    t2_neg_log_pvalue: float
    t2_beta: float
    t2_stderr_beta: float
    t2_alt_allele_freq: float

    @property
    def marker(self) -> str:
        """Specify the marker in a string format compatible with UM LD server and other variant-specific requests"""
        ref_alt = '_{}/{}'.format(self.ref, self.alt) \
            if (self.ref and self.alt) else ''
        return '{}:{}{}'.format(self.chrom, self.pos, ref_alt)


def merge_variants_in_region(a: ty.Iterator[BasicVariant], b: ty.List[BasicVariant]):
    """
    Merge two iterators of the same variant (like marg + cond, or trait1 / trait2, etc)

    ASSUMES:
     - always same chromosome (only pos/ref/alt may differ)
     - inner join (excludes any variant not in both)
    """
    a = iter(a)
    b = iter(b)
    # Simplifying assumption: these are iterators over tabix region data
    #   (always the same chromosome, only pos / ref/ alt may differ)

    try:
        a_i = next(a)
        b_i = next(b)
    except StopIteration:
        # If one iterator is empty, then so is the inner join, because there is nothing to align
        return []

    a_multi = {}
    b_multi = {}
    joined = []


    def flush():
        """
        Two aligned files might have multiple allele forms at same position, and not always be sorted
        Whenever we move past a position, merge all the forms of a variant from that spot
        """
        nonlocal a_multi
        nonlocal b_multi
        for k, a_i in a_multi.items():
            if k in b_multi:
                # merge the two variants
                b_i = b_multi[k]
                joined.append(
                    MergedVariant(
                        a_i.chrom, a_i.pos, a_i.ref, a_i.alt,
                        a_i.neg_log_pvalue, a_i.beta, a_i.stderr_beta, a_i.alt_allele_freq,
                        b_i.neg_log_pvalue, b_i.beta, b_i.stderr_beta, b_i.alt_allele_freq,
                    )
                )

        # After we've joined what variants can be joined, clear the lists of variants at this position
        # Eg, this is done when moving on to another position
        a_multi = {}
        b_multi = {}

    while True:
        try:
            cmp = a_i.pos - b_i.pos
            if cmp < 0:
                a_i = next(a)
                flush()
                continue
            elif cmp > 0:
                b_i = next(b)
                flush()
                continue
            else:
                a_multi[f'{a_i.ref}_{a_i.alt}'] = a_i
                b_multi[f'{b_i.ref}_{b_i.alt}'] = b_i
                a_i = next(a)
                b_i = next(b)
        except StopIteration:
            # If any attempt to advance iterators fails, then we've found all the records that can be merged
            flush()
            return joined

    flush()
    return joined


def serialize_neg_log_pvalue(value: float) -> ty.Union[float, str, None]:
    """
    Many GWAS programs suffer from underflow and may represent small p=0/-logp=inf

    The JSON standard can't handle "Infinity", but the string 'Infinity' can be type-coerced by JS, eg +value
    Therefore we serialize this as a special case so it can be used in the frontend
    """
    if value is not None and math.isinf(value):
        return 'Infinity'
    else:
        return value
