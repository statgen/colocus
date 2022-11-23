from zorp.parsers import BasicVariant

from colocus.api.util import MergedVariant, merge_variants_in_region

a = [
    # BasicVariant(chrom, pos, rsid, ref, alt, neg_log_pvalue, beta, stderr_beta, alt_allele_freq)
    BasicVariant('12', 1, None, 'A', 'C', 10, 1, 2, 2),
    BasicVariant('12', 5, None, 'A', 'C', 11, 1, 2, 2),  # multiallelic at position
    BasicVariant('12', 5, None, 'A', 'G', 12, 1, 2, 2),
    BasicVariant('12', 18, None, 'A', 'C', 13, 1, 2, 2),
]

b = [
    # Different length than a
    BasicVariant('12', 5, None, 'A', 'G', 21, 1, 2, 2),  # multiallelic at position-sorted in different order than a
    BasicVariant('12', 5, None, 'A', 'C', 22, 1, 2, 2),
    BasicVariant('12', 9, None, 'A', 'C', 23, 1, 2, 2),  # not in a (need to advance both a and b at different times)
]


def test_merged_variants():
    joined = merge_variants_in_region(a, b)
    expected = [
        MergedVariant('12', 1, 'A', 'C', 10, 1, 2, 2, None, None, None, None),
        MergedVariant('12', 5, 'A', 'C', 11, 1, 2, 2, 22, 1, 2, 2),
        MergedVariant('12', 5, 'A', 'G', 12, 1, 2, 2, 21, 1, 2, 2),
        MergedVariant('12', 18, 'A', 'C', 13, 1, 2, 2, None, None, None, None),
    ]

    assert joined == expected
