from dataclasses import dataclass


@dataclass
class LDContainer:
    chr_a: str
    bp_a: int
    snp_a: str
    chr_b: str
    bp_b: int
    snp_b: str
    r2: float


def parse_plink(line: str):
    """
    Parse PLINK format LD

    NOTE: PLINK files vary. They should be harmonized into a consistent set of columns during ingest.
    This parser assumes the following columns (plus any on the right after that):
    CHR_A	BP_A	SNP_A	CHR_B	BP_B	SNP_B	R2
    """
    fields = line.strip().split('\t')
    chr_a, bp_a, snp_a, chr_b, bp_b, snp_b, r2, _ = fields
    bp_a = int(bp_a)
    bp_b = int(bp_b)
    r2 = float(r2)
    return LDContainer(chr_a, bp_a, snp_a, chr_b, bp_b, snp_b, r2)
