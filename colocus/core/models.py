"""
Core models describing key data entities
"""
from django.db import models

from ..api.util import sign
from . import constants

# from model_utils.models import SoftDeletableModel, TimeStampedModel


class DataSubmission(models.Model):
    """
    A group of colocalization analyses, individual study summary statistics (marginal and conditional analyses), and
    fine-mapping results that have been submitted together by a collaborator or group.
    """
    uuid = models.TextField(
        blank=False,
        null=False,
        unique=True,
        help_text='A stable unique identifier for this dataset, should be specified on ingest')

    description = models.TextField(
        help_text='A human-readable description of the dataset, like "Colocalization & fine-mapping of adipose eQTLs"',
        null=True,
        blank=True,
        unique=False)

    ingest_date = models.DateTimeField(
        auto_now_add=True,
        null=True,
        help_text='Date when this dataset was loaded into the site')

    # We only collect this for the coloc (not upstream data) because upstream contacts may not be involved with the site
    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text='Contact of record to report problems / questions about this data submission')

    publication = models.ForeignKey(
        'Publication',
        on_delete=models.CASCADE,
        null=True,
        help_text='Publication describing this overall data submission')

    # Computed properties used by serializers
    @property
    def trait_count(self):
        # marginalanalysis_set is an automatically generated Django reverse relation field due to the fact that
        # MarginalAnalysis has a ForeignKey to DataSubmission
        return self.marginalanalysis_set.count()


class Person(models.Model):
    """
    Model for a person. This can be used to track the analyst who actually created a dataset, or the person
    who submitted the dataset to the site, or the PI of a study, etc.
    """
    orcid = models.TextField(
        help_text='ORCID of the analyst',
        null=False,
        blank=False,
        unique=True)

    name = models.TextField(
        help_text='Name of the analyst',
        null=False,
        blank=False,
        unique=False)

    email = models.EmailField(
        help_text='Email address of the analyst',
        null=False,
        blank=False,
        unique=False)

    institution = models.TextField(
        help_text='Institution of the analyst',
        null=True,
        blank=True,
        unique=False)


class Dataset(models.Model):
    """
    A dataset contains analyses on multiple traits from a single study. For example, METSIM may run a GWAS on 1 or 100
    traits, or perform eQTL analysis on thousands of genes (traits).
    """
    uuid = models.TextField(
        blank=False,
        null=False,
        unique=True,
        help_text='A stable unique identifier for this dataset, should be specified on ingest')

    data_submission = models.ForeignKey(
        DataSubmission,
        on_delete=models.CASCADE,
        null=False,
        help_text='Data submission that this dataset belongs to')

    analysts = models.ManyToManyField(
        Person,
        help_text='Analysts who created this dataset',
        related_name='datasets_as_analyst')

    submitter = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        null=False,
        help_text='Person who submitted this dataset to the site',
        related_name='datasets_as_submitter')

    principal_investigators = models.ManyToManyField(
        Person,
        help_text='Principal investigators of the study that produced this dataset',
        related_name='datasets_as_pi')

    publication = models.ForeignKey(
        'Publication',
        on_delete=models.CASCADE,
        null=True,
        help_text='Publication describing this overall dataset')

    analysis_type = models.TextField(
        choices=constants.ANALYSIS_TYPES,
        help_text="Type of association analysis - GWAS, eQTL, pQTL, ATAC-seq, methylation, etc.")

    genome_build = models.TextField(
        choices=constants.GENOME_BUILDS,
        help_text="Genome build used for all analyses in this dataset")

    n_traits = models.PositiveIntegerField(
        default=0,
        help_text='Number of traits analyzed in this dataset')

    n_traits_with_sig = models.PositiveIntegerField(
        default=0,
        help_text='Number of traits with at least one signal')

    tissue = models.TextField(
        help_text='Tissue type for all analyses in this dataset (if applicable), e.g. "adipose" or "liver"',
        null=True,
        blank=True,
        unique=False)

    ancestry = models.TextField(
        null=True,
        blank=True,
        help_text='Ancestry of the samples used for analyses in this dataset, e.g. "EUR"')

    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text='Contact of record to report problems / questions about this dataset')

    external_link = models.URLField(
        blank=True,
        null=True,
        help_text='URL for where the data was downloaded from. Used to track provenance.')


class LDStats(models.Model):
    """
    Linkage disequilibrium (LD) statistics for a particular population / dataset / genome build.
    """

    uuid = models.TextField(
        blank=False,
        null=False,
        unique=True,
        db_index=True,
        help_text='A stable unique identifier for this entity. Should be specified on ingest.')

    data_submission = models.ForeignKey(
        DataSubmission,
        on_delete=models.CASCADE,
        null=False,
        help_text='Data submission that this LD data was provided with')

    panel = models.TextField(help_text='Name of LD panel used (eg 1000G)')
    population = models.TextField(help_text='Name of population (eg EUR)')
    genome_build = models.TextField(choices=constants.GENOME_BUILDS)

    ld_data = models.TextField(
        verbose_name='LD data',
        help_text='Absolute path to PLINK formatted LD data (relative to at least key signal SNPs). '
                  'Must be compressed with bgzip')

    ld_data_tbi = models.TextField(
        verbose_name='LD tabix index',
        help_text='Absolute path to Tabix index for the LD data. Must match the bgzip file')


class Study(models.Model):
    """
    A study is a research group or consortium that has produced one or more analyses.
    """
    uuid = models.TextField(
        blank=False,
        null=False,
        unique=True,
        db_index=True,
        help_text='A stable unique identifier for this entity. Should be specified on ingest.')

    description = models.TextField(
        help_text='A description of the study, e.g. "Global Lipids Genetics Consortium"',
        null=True,
        blank=True,
        unique=False)


class Phenotype(models.Model):
    uuid = models.TextField(
        blank=False,
        null=False,
        unique=True,
        db_index=True,
        help_text='Universally unique identifier')

    efo_id = models.TextField(
        blank=False,
        null=True,
        unique=False,
        help_text='External ID in EFO for the trait, e.g. "EFO_0001360" or "MONDO_0005148"')

    kp_id = models.TextField(
        blank=False,
        null=True,
        unique=False,
        help_text='External ID in AMP knowledge portal for the trait, e.g. "T2DadjBMI"')

    name = models.TextField(
        help_text='Full name of the trait, e.g. "Body Mass Index" or "Fasting glucose adjusted for BMI"',
        null=False,
        blank=False,
        unique=False)


class Gene(models.Model):
    ens_id = models.TextField(null=False, blank=False, db_index=True, unique=True, help_text="Ensembl ID")

    symbol = models.TextField(null=False, blank=False, db_index=True, help_text="HGNC symbol")
    chrom = models.TextField(null=True, blank=False, help_text="Chromosome")
    start = models.PositiveIntegerField(null=True, blank=False, help_text="Start position of the gene")
    end = models.PositiveIntegerField(null=True, blank=False, help_text="End position of the gene")


class Exon(models.Model):
    ens_id = models.TextField(
        null=False, blank=False, db_index=True, unique=True,
        help_text="Ensembl ID of the exon, or Ensembl ID of the gene + exon coordinates, e.g. ENSG00000141510.15_1_100")

    gene = models.ForeignKey(
        Gene, on_delete=models.CASCADE,
        help_text="The gene to which this exon belongs",
        related_name="exons")

    chrom = models.TextField(null=True, blank=False, help_text="Chromosome")
    start = models.PositiveIntegerField(null=True, blank=False, help_text="Start position of the exon")
    end = models.PositiveIntegerField(null=True, blank=False, help_text="End position of the exon")


class Trait(models.Model):
    """
    A trait is a phenotype or other biological property that has been studied in one or more analyses. This could be a
    phenotype like type 2 diabetes, or a gene expression trait like "expression of gene X".
    """

    uuid = models.TextField(
        blank=False,
        null=False,
        unique=True,
        db_index=True,
        help_text='Universally unique identifier')

    biomarker_type = models.TextField(
        help_text="Type of biomarker, e.g. phenotype or gene-expression exon-expression or methylation or atac-seq",
        null=False,
        blank=False,
        unique=False)

    gene = models.ForeignKey(
        Gene,
        on_delete=models.CASCADE,
        related_name='trait',
        null=True
    )

    exon = models.ForeignKey(
        Exon,
        on_delete=models.CASCADE,
        related_name='trait',
        null=True
    )

    phenotype = models.ForeignKey(
        Phenotype,
        on_delete=models.CASCADE,
        related_name='trait',
        null=True
    )


class Publication(models.Model):
    """
    A publication is a record of a scientific article that describes one or more analyses.
    """

    uuid = models.TextField(
        blank=False,
        null=False,
        unique=True,
        db_index=True,
        help_text='A stable unique identifier for this entity. Should be specified on ingest.')

    pmid = models.PositiveIntegerField(
        blank=True,
        null=True,
        unique=False,
        db_index=True,
        help_text='PubMed ID for the publication')

    doi = models.TextField(
        blank=True,
        null=True,
        unique=False,
        db_index=True,
        help_text='Digital Object Identifier for the publication')

    authors = models.TextField(
        null=True,
        help_text='Free-text author list, eg "ACRONYM Consortium" or "Mendel et al" (used for display only)')

    title = models.TextField(
        blank=True,
        null=True,
        help_text='Title of the publication')

    year = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Year of publication')

    journal = models.TextField(
        blank=True,
        null=True,
        help_text='Journal of publication')


class MarginalAnalysis(models.Model):
    """
    Marginal summary statistics for one study (GWAS, QTL, etc) and one trait (T2D, gene expression of TCF7L2, etc.)
    """

    uuid = models.TextField(
        blank=False,
        null=False,
        unique=True,
        db_index=True,
        help_text='A stable unique identifier for this analysis'
    )

    data_submission = models.ForeignKey(
        DataSubmission,
        on_delete=models.CASCADE,
        null=False,
        help_text='Analysis was part of this data submission'
    )

    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        null=False,
        related_name='marginal_analyses',
        help_text='Analysis was part of this dataset')

    analysis_type = models.TextField(
        choices=constants.ANALYSIS_TYPES,
        help_text="Type of association analysis - GWAS, eQTL, pQTL, ATAC-seq, methylation, etc.")

    genome_build = models.TextField(
        choices=constants.GENOME_BUILDS,
        help_text="Genome build used for this analysis (positions of variants)")

    trait = models.ForeignKey(
        Trait,
        on_delete=models.CASCADE,
        null=False,
        help_text='The trait analyzed in this analysis')

    tissue = models.TextField(
        help_text='Tissue or cell type in which this analysis\' trait was analyzed, e.g. "adipose" or "liver"',
        null=True,
        blank=True,
        unique=False)

    study = models.ForeignKey(
        Study,
        on_delete=models.CASCADE,
        null=False,
        help_text='The study that produced this analysis')

    ancestry = models.TextField(
        null=True,
        blank=True,
        help_text='Ancestry of the samples used in this analysis, e.g. "EUR"')

    ld = models.ForeignKey(
        LDStats,
        on_delete=models.CASCADE,
        null=False,
        help_text='LD panel to be used with this dataset'
    )

    # Files that must be present. All are generated during an ingest pipeline step.
    summary_stats = models.TextField(
        verbose_name='Marginal summary stats',
        help_text='Absolute path to the marginal summary stats for this study. Must be compressed with bgzip')

    summary_stats_tbi = models.TextField(
        verbose_name='Tabix index for summary stats',
        help_text='Absolute path to Tabix index for summary stats (.tbi file). Must match bgzip file.')

    manhattan_bins = models.TextField(
        verbose_name='Binned data for manhattan plots',
        help_text='Absolute path to results of manhattan plot binning process')

    qq_bins = models.TextField(
        verbose_name='Binned data for QQ plots',
        help_text='Absolute path to results of manhattan plot binning process')

    description = models.TextField(
        help_text='Freetext with important info such as analysis parameters. In the future, some parameters might '
                  'be tracked as part of the DB schema.')

    publication = models.ForeignKey(
        Publication,
        on_delete=models.CASCADE,
        null=True,
        help_text='The publication describing this analysis')

    external_link = models.URLField(
        blank=True,
        null=True,
        help_text='URL for where the data was downloaded from. Used to track provenance.')


class LeadVariant(models.Model):
    """
    The lead variant from a fine-mapped signal.
    """

    vid = models.TextField(help_text="Full variant ID in chr_pos_ref_alt format.")
    chrom = models.TextField(db_collation="uint")
    pos = models.PositiveIntegerField(help_text="Position of the variant in the genome")
    ref = models.TextField(help_text='Reference allele')
    alt = models.TextField(help_text='Alternate allele. This must also be the effect allele.')


class FineMappingProgram(models.Model):
    """
    A program used to perform fine-mapping or conditional analysis of a marginal association analysis. Usually this
    process is performed by SuSiE, APEX, FINEMAP, or GCTA.
    """

    name = models.TextField(
        blank=False,
        null=False,
        unique=False,
        help_text='Name of the fine-mapping program, e.g. "SuSiE" or "FINEMAP"')

    version = models.TextField(
        blank=False,
        null=True,
        help_text='Version of the fine-mapping program, e.g. "v1.0.0"')


class FineMappedSignal(models.Model):
    """
    One specific signal after fine-mapping or conditional analysis of a marginal association analysis. Usually this
    process is performed by SuSiE, APEX, FINEMAP, or GCTA.
    """

    uuid = models.TextField(
        blank=False,
        null=False,
        unique=True,
        db_index=True,
        help_text='A stable unique identifier for this entity. Should be specified on ingest')

    analysis = models.ForeignKey(
        MarginalAnalysis,
        on_delete=models.CASCADE,
        null=False,
        help_text='The analysis in which this signal was identified')

    program = models.ForeignKey(
        FineMappingProgram,
        on_delete=models.CASCADE,
        null=False,
        help_text='The program used to perform the fine-mapping or conditional analysis')

    cond_analysis = models.TextField(
        verbose_name='Cond analysis results',
        help_text='Absolute path to conditional (or "all but one") analysis of marginal results '
                  '(rel to lead variant of this signal)')

    cond_analysis_tbi = models.TextField(
        verbose_name='tbi for cond results',
        help_text='Absolute path to Tabix index; must match the conditional analysis file')

    # Lead variant
    lead_variant = models.ForeignKey(
        LeadVariant, on_delete=models.CASCADE,
        help_text="Lead variant of the fine-mapped signal.")

    neg_log_p = models.FloatField(help_text="Conditional or fine-mapped -log10p value.")
    effect_marg = models.FloatField(help_text='Effect size in the marginal analysis')
    effect_cond = models.FloatField(help_text='Effect size in the conditional/fine-mapping analysis')
    se_cond = models.FloatField(help_text='Conditional standard error of the effect size')

    cond_minp_variant = models.TextField(
        null=True,
        help_text="Variant with the smallest p-value after conditional analysis. Often the lead_variant* fields above"
                  "pertain to the variant that was reported in a GWAS publication, but that does not necessarily mean"
                  "that variant will also be the most significant in the conditional analysis."
    )

    is_marg = models.BooleanField(
        default=False,
        null=False,
        help_text="True if this signal's summary statistics are from the marginal analysis, not a conditional analysis."
                  " This can happen in cases where the marginal analysis is the only analysis (no conditional analysis"
                  " was needed) or if there was a problem in fine-mapping at this particular locus")


class ColocResult(models.Model):
    """
    Colocalization results for one specific pair of signals across two traits
    """

    uuid = models.CharField(
        max_length=32,
        blank=False,
        null=False,
        unique=True,
        db_index=True,
        help_text='A stable unique identifier for this entity. Should be specified on ingest.'
    )

    data_submission = models.ForeignKey(
        DataSubmission,
        on_delete=models.CASCADE,
        null=False,
        help_text='This signal was identified as part of a specific bulk colocalization analysis'
    )

    signal1 = models.ForeignKey(
        FineMappedSignal,
        related_name="+",  # do not create reverse relation, not needed
        on_delete=models.CASCADE,
        null=False,
        help_text='The first signal (from trait 1)',
    )

    signal2 = models.ForeignKey(
        FineMappedSignal,
        related_name="+",
        on_delete=models.CASCADE,
        null=False,
        help_text='The second signal (from trait 2)'
    )

    cross_signal = models.JSONField(
        null=True,
        help_text="Contains information about each signal and its lead variant's effect in the other signal's "
                  "summary statistics"
    )

    # How standard are these names? Is there a more descriptive term?
    coloc_h3 = models.FloatField(
        verbose_name='H3',
        help_text='Probability that both traits are associated, but with different causal variants'
    )
    coloc_h4 = models.FloatField(
        verbose_name='H4',
        help_text='Probability that both traits are associated, with same causal variant'
    )

    r2 = models.FloatField(
        null=True,
        help_text='R2 between the two signals\' lead variants'
    )

    n_coloc_between_traits = models.PositiveIntegerField(
        null=True,
        help_text='Number of colocalizations in total between the two traits for this gene or locus in the overall '
                  'dataset'
    )

    @property
    def marg_cond_flip(self):
        return (sign(self.signal1.effect_cond) != sign(self.signal1.effect_marg)) or \
            (sign(self.signal2.effect_cond) != sign(self.signal2.effect_marg))
