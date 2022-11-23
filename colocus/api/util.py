import dataclasses
import math
import typing as ty
from typing import Union

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
    t1_neg_log_pvalue: Union[float, None]
    t1_beta: Union[float, None]
    t1_stderr_beta: Union[float, None]
    t1_alt_allele_freq: Union[float, None]

    # Dataset / trait 2
    t2_neg_log_pvalue: Union[float, None]
    t2_beta: Union[float, None]
    t2_stderr_beta: Union[float, None]
    t2_alt_allele_freq: Union[float, None]

    @property
    def marker(self) -> str:
        """Specify the marker in a string format compatible with UM LD server and other variant-specific requests"""
        ref_alt = '_{}/{}'.format(self.ref, self.alt) \
            if (self.ref and self.alt) else ''
        return '{}:{}{}'.format(self.chrom, self.pos, ref_alt)


def merge_variants_in_region(a: ty.List[BasicVariant], b: ty.List[BasicVariant]):
    """
    Merge two iterators of the same variant (like marg + cond, or trait1 / trait2, etc)

    ASSUMES:
     - always same chromosome (only pos/ref/alt may differ)
     - left join (includes all variants from a; variants from b that are in a are also included)
    """
    variants = {}
    joined = []

    def vkey(v):
        return f"{v.chrom}_{v.pos}_{v.ref}_{v.alt}"

    for v in a:
        variants[vkey(v)] = {"marg": v}

    for v in b:
        vk = vkey(v)
        if vk in variants:
            variants[vk]["cond"] = v

    for vid, v in variants.items():
        a_i = v["marg"]

        if "cond" in v:
            b_i = v["cond"]
        else:
            b_i = BasicVariant(a_i.chrom, a_i.pos, a_i.rsid, a_i.ref, a_i.alt, None, None, None, None)

        joined.append(
            MergedVariant(
                a_i.chrom, a_i.pos, a_i.ref, a_i.alt,
                a_i.neg_log_pvalue, a_i.beta, a_i.stderr_beta, a_i.alt_allele_freq,
                b_i.neg_log_pvalue, b_i.beta, b_i.stderr_beta, b_i.alt_allele_freq,
            )
        )

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
