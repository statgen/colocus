"""
Core models describing key data entities
"""
import os

from django.db import models
from model_utils.models import SoftDeletableModel, TimeStampedModel

from . import constants


class AnalysisGroup(models.Model):
    """
    A group of colocalization analyses, like a paper that performs the same pipeline on a thousand distinct signals
    across many gwas-eqtl pairs
    """
    # TODO In future add unique constraints: make the IDfield a uuid or such to prevent collisions across projects.
    uuid = models.CharField(
        max_length=32,
        blank=False,
        null=False,
        unique=True,
        help_text='A stable unique identifier for this dataset, should be specified on ingest'
    )

    # User-provided study metadata
    ingest_complete = models.DateTimeField(
        auto_now_add=True,
        null=True,
        help_text='Date when this dataset was loaded into the site'
    )
    study_date = models.DateField(null=False, blank=False,
                                  help_text='Author provided date when the analysis was performed')

    authors = models.TextField(
        help_text='Free-text author list, eg "ACRONYM Consortium" or "Mendel et al" (used for display only)'
    )

    # We only collect this for the coloc (not upstream data) because upstream contacts may not be involved with the site
    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text='Contact of record to report problems / questions about this analysis'
    )

    pmid = models.CharField(max_length=20,
                            blank=True,
                            null=True,
                            help_text='Identify a publication describing this colocalization analysis',
                            verbose_name='PMID')


class LDPairs(models.Model):
    """LD data for a particular population / dataset/ genome build."""
    analysis = models.ForeignKey(
        AnalysisGroup,
        on_delete=models.SET_NULL,
        null=False,
        help_text='This LD was provided for a specific analysis'
    )

    uuid = models.CharField(
        max_length=32,
        blank=False,
        null=False,
        unique=True,
        help_text='A stable unique identifier for this entity. Should be specified on ingest.'
    )

    panel = models.CharField(max_length=32, help_text='Name of LD panel used (eg 1000G)')
    population = models.CharField(max_length=32, help_text='Name of population (eg EUR)')
    genome_build = models.CharField(max_length=10, choices=constants.GENOME_BUILDS)


class MarginalTrait(models.Model):
    """
    Marginal summary statistics for one study (GWAS, QTL, etc)
    """
    uuid = models.CharField(
        max_length=32,
        blank=False,
        null=False,
        unique=True,
        help_text='A stable unique identifier for this entity. Should be specified on ingest'
    )

    #### Basic properties that define the dataset
    trait_type = models.CharField(max_length=10, choices=constants.TRAIT_TYPES)
    genome_build = models.CharField(max_length=10, choices=constants.GENOME_BUILDS)
    # JSON field consisting of {trait} for gwas ; {gene, tissue} for eQTL
    metadata = models.JSONField(help_text='Additional trait-type specific information. Eg {trait} for GWAS, or { gene, tissue } for eQTL')

    #### Files that must be present. All are generated during an ingest pipeline step.
    summary_stats = models.FileField(
        upload_to=lambda self: os.path.join('marginal', self.uuid, 'marginal.gz'),
        verbose_name='Marginal summary stats',
        help_text='The marginal summary stats for this study. Must be compressed with bgzip'
    )

    summary_stats_tbi = models.FileField(
        upload_to=lambda self: os.path.join('marginal', self.uuid, 'marginal.gz.tbi'),
        verbose_name='Tabix index for summary stats',
        help_text='Tabix index for summary stats (.tbi file). Must match bgzip file.'
    )

    ld_data = models.FileField(
        upload_to=lambda self: os.path.join('marginal', self.uuid, 'ld.gz'),
        verbose_name='LD data',
        help_text='PLINK formatted LD data (relative to at least key signal SNPs). Must be compressed with bgzip'
    )

    ld_data_tbi = models.FileField(
        upload_to=lambda self: os.path.join('marginal', self.uuid, 'ld.gz.tbi'),
        verbose_name='LD tabix index',
        help_text='Tabix index for the LD data. Must match the bgzip file'
    )

    manhattan_bins = models.FileField(
        upload_to=lambda self: os.path.join('marginal', self.uuid, 'manhattan.json'),
        verbose_name='Binned data for manhattan plots',
        help_text='Results of manhattan plot binning process'
    )

    qq_bins = models.FileField(
        upload_to=lambda self: os.path.join('marginal', self.uuid, 'qq.json'),
        verbose_name='Binned data for QQ plots',
        help_text='Results of manhattan plot binning process'
    )

    #### Things used for search and provenance
    study_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text='Name of the parent study (like "GLGC" or "GTEx") that produced the dataset'
    )

    label = models.TextField(help_text='A human-readable description of the dataset, like "Body Mass Index"')
    description = models.TextField(
        help_text='Freetext with important info such as analysis parameters. In the future, some parameters might '
                  'be tracked as part of the DB schema.')

    pmid = models.CharField(max_length=20,
                            blank=True,
                            null=True,
                            help_text='The publication describing this trait analysis',
                            verbose_name='PMID')

    authors = models.TextField(
        help_text='Free-text author list, eg "ACRONYM Consortium" or "Mendel et al" (used for display only)'
    )

    external_link = models.URLField(
        blank=True,
        null=True,
        help_text='URL for where the data was downloaded from. Used to track provenance.'
    )


class MarginalSignal(models.Model):
    """
    One specific signal in one specific trait. This specifies the signal, as well as things like conditional
     analysis of the marginal trait in a nearby region.
    """
    analysis = models.ForeignKey(
        AnalysisGroup,
        on_delete=models.SET_NULL,
        null=False,
        help_text='This signal was identified as part of a specific bulk colocalization analysis'
    )

    trait = models.ForeignKey(
        MarginalTrait,
        on_delete=models.SET_NULL,
        null=False,
        help_text='The trait in which this signal was identified'
    )

    cond_analysis = models.FileField(
        upload_to=lambda self: os.path.join('signals', self.uuid, 'cond_analysis.gz'),
        verbose_name='Cond analysis results ',
        help_text='Conditional (or "all but one") analysis of marginal results (rel to lead variant of this signal)'
    )

    cond_analysis_tbi = models.FileField(
        upload_to=lambda self: os.path.join('signals', self.uuid, 'cond_analysis.gz.tbi'),
        verbose_name='tbi for cond results',
        help_text='Tabix index; must match the conditional analysis file'
    )

    #### Human readable description of lead variant. Explicit cp are required to support search by region
    lead_variant_chrom = models.CharField(max_length=5, blank=False, null=False)
    lead_variant_pos = models.PositiveIntegerField()
    lead_variant_marker = models.CharField(
        max_length=5, blank=False, null=False,
        help_text='Specifier of the form chrom:pos_ref/alt. Used for display only')
    lead_variant_neg_log_p = models.FloatField(
        help_text="Marginal -log10p value for lead variant. Used for display purposes.")
    lead_variant_nearest_gene = models.CharField(
        max_length=50,
        help_text='Human-friendly name of the closest gene. Used for display purposes.'
    )


class ColocPair(models.Model):
    """
    Colocalization results for one specific pair of signals across two traits
    """
    uuid = models.CharField(
        max_length=32,
        blank=False,
        null=False,
        unique=True,
        help_text='A stable unique identifier for this entity. Should be specified on ingest.'
    )

    analysis = models.ForeignKey(
        AnalysisGroup,
        on_delete=models.SET_NULL,
        null=False,
        help_text='This signal was identified as part of a specific bulk colocalization analysis'
    )

    signal1 = models.ForeignKey(
        MarginalSignal,
        on_delete=models.SET_NULL,
        null=False,
        help_text='The first signal (from trait 1)'
    )

    signal2 = models.ForeignKey(
        MarginalSignal,
        on_delete=models.SET_NULL,
        null=False,
        help_text='The second signal (from trait 2)'
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
