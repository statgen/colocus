import os
import typing as ty
from typing import Union

from django.conf import settings
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import exceptions as drf_exceptions
from rest_framework import generics
from zorp.readers import TabixReader
from zorp.sniffers import guess_gwas_standard

from colocus.core import models

from . import filters, parsers, serializers, util


# Base classes shared among views
# --------------------------------
class TabixRegionView(generics.RetrieveAPIView):
    def get_serializer(self, *args, **kwargs):
        """Unique scenario: a single model that returns a list of records"""
        return super(TabixRegionView, self).get_serializer(*args, many=True, **kwargs)

    def _query_params(self) -> ty.Tuple[str, int, int]:
        """
        Specific rules for basic region query:
        - Must specify chrom, start, end, and variant as query params
        - start and end must be integers
        - end > start
        - 0 <= (end - start) <= MAX_REGION_SIZE
        """
        params = self.request.query_params

        chrom: Union[str, None] = params.get('chrom', None)
        start: Union[str, int, None] = params.get('start', None)
        end: Union[str, int, None] = params.get('end', None)

        if not (chrom and start and end):
            raise drf_exceptions.ParseError('Must specify "chrom", "start", and "end" as query parameters')

        try:
            start = int(start)
            end = int(end)
        except ValueError:
            raise drf_exceptions.ParseError('"start" and "end" must be integers')

        start = max(0, start)

        if end <= start:
            raise drf_exceptions.ParseError('"end" position must be greater than "start"')

        if not (0 <= (end - start) <= settings.LZ_MAX_REGION_SIZE):
            raise drf_exceptions.ParseError(
                f'Cannot handle requested region size. Max allowed is {settings.LZ_MAX_REGION_SIZE}')

        return chrom, start, end


# Collect a list of possible ordering/sorting fields for documenting the API below.
order_options = sorted([
    f"\n * `{field[0]}`"
    for field in filters.ColocResultFilter.base_filters.get('ordering').field.choices
    if field and (not field[0].startswith("-")) and (not field[0] == '')
])


@extend_schema(
    parameters=[
        OpenApiParameter(
            name='ordering',
            description=(
                'Use the following options for ordering/sorting results: '
                + ''.join(order_options) + '\n\n'
                + 'H4 is posterior probability of colocalization '
                  '(i.e. the two signals share the same causal variant).\n'
            ),
            required=False,
            type=str
        ),
        OpenApiParameter(
            name='uuid',
            description='Filter results by coloc result UUID',
            required=False,
            type=str
        ),
    ],
    examples=[
        OpenApiExample(
            'Example of filtering on H4 > some value and sorting',
            summary='Example GET request with sorting',
            description='This is an example of a GET request with sorting by coloc_h4.',
            value={
                'ordering': '-coloc_h4',
                'coloc_h4__gte': 0.95
            },
            request_only=True,
        ),
    ]
)
class ColocResultListView(generics.ListAPIView):
    """
    ## List colocalization results

    This endpoint provides a list of `ColocResult`. Each result represents one colocalization result, which is
    the result of colocalizing two fine-mapped signals from a GWAS or eQTL analysis.
    """

    queryset = (
        models.ColocResult.objects
        .select_related(
            'signal1', 'signal2',
            'signal1__analysis', 'signal2__analysis',
            'signal1__analysis__trait', 'signal2__analysis__trait',
            'signal1__lead_variant', 'signal2__lead_variant',
            'signal1__analysis__trait__gene', 'signal2__analysis__trait__gene',
            'signal1__analysis__trait__exon', 'signal2__analysis__trait__exon',
            'signal1__analysis__trait__phenotype', 'signal2__analysis__trait__phenotype',
            'signal1__analysis__study', 'signal2__analysis__study',
            'signal1__analysis__publication', 'signal2__analysis__publication',)
        .prefetch_related(
            'signal1__analysis__ld', 'signal2__analysis__ld'))

    serializer_class = serializers.ColocResultSerializer
    filterset_class = filters.ColocResultFilter


class ColocResultDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.ColocResult.objects.select_related('signal1', 'signal2')
    serializer_class = serializers.ColocResultSerializer


class LDStatsListView(generics.ListAPIView):
    ordering = ('panel', 'population')
    queryset = models.LDStats.objects.all()
    serializer_class = serializers.LDStatsSerializer


class LDStatsDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.LDStats.objects.all()
    serializer_class = serializers.LDStatsSerializer


class FinemappedSignalListView(generics.ListAPIView):
    """
    ## List fine-mapped signals

    This endpoint provides a list of all fine-mapped signals across all analyses in the database.

    A fine-mapping program like SuSiE or FINEMAP takes GWAS or eQTL summary statistics (for a single gene) in a
    particular region and outputs a list of independent signals, where each signal is a credible set of variants that
    are likely to be "causal" for the trait.

    Each signal has a lead variant, which is the variant with the strongest association in the set. However, it
    is possible for there to be more than one lead variant (with equivalent posterior probability of being causal), but
    we only use one as the sentinel variant for the signal.
    """
    queryset = (
        models.FineMappedSignal.objects
        .select_related(
            'analysis',
            'analysis__trait',
            'analysis__trait__phenotype',
            'analysis__study',
            'analysis__ld',
            'analysis__publication',
            'lead_variant')
        .prefetch_related(
            'coloc1',
            'coloc1__signal1',
            'coloc1__signal2',
            'coloc2',
            'coloc2__signal1',
            'coloc2__signal2'))

    serializer_class = serializers.FinemappedSignalSerializer
    filterset_class = filters.FinemappedSignalFilter


class FinemappedSignalDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.FineMappedSignal.objects.select_related(
        'analysis', 'analysis__trait', 'analysis__study', 'analysis__ld', 'lead_variant')
    serializer_class = serializers.FinemappedSignalSerializer


class MarginalAnalysisListView(generics.ListAPIView):
    """
    ## List marginal analyses

    A marginal analysis, sometimes shortened to just 'analysis', represents a marginal association scan
    for a single trait. It is the output of GWAS or eQTL analysis for one trait or gene. In a marginal analysis, no
    other variants have been conditioned on. The association test is:

    ```
    trait ~ variant + covariates
    ```

    This is often provided as a single file, with summary statistics for every variant's association with the trait
    (p-value, beta, se, etc.)
    """

    queryset = models.MarginalAnalysis.objects.select_related(
        'trait', 'trait__gene', 'trait__exon', 'trait__phenotype', 'study', 'publication', 'ld')
    serializer_class = serializers.MarginalAnalysisSerializer


class MarginalAnalysisDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.MarginalAnalysis.objects.select_related('data_submission')
    serializer_class = serializers.MarginalAnalysisSerializer


class TraitListView(generics.ListAPIView):
    """
    ## List of traits across all analyses in the database.

    A trait is a phenotype, gene expression trait, or other response/outcome variable that was analyzed in a marginal
    GWAS or eQTL analysis.

    A phenotype may be any non-molecular measured trait, such as height, BMI, T2D affection status, etc.
    """

    queryset = models.Trait.objects.select_related('gene', 'exon', 'phenotype')
    serializer_class = serializers.TraitSerializer


class TraitDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.Trait.objects.select_related('gene', 'exon', 'phenotype')
    serializer_class = serializers.TraitSerializer


class StudyListView(generics.ListAPIView):
    """
    ## List of studies

    Each analysis is conducted by a `Study`, which represents the group of researchers who conducted the analysis. This
    may be a consortium, such as "DIAGRAM", or a single study group, such as "UK Biobank" or "FUSION".
    """

    ordering = ('uuid',)
    queryset = models.Study.objects.all()
    serializer_class = serializers.StudySerializer


class StudyDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.Study.objects.all()
    serializer_class = serializers.StudySerializer


# Tabix-based "region view" endpoints
# -------------------------------------
class FinemappedSignalSummRegionView(TabixRegionView):
    """Provide all summary stats associated with a particular signal (marginal + conditional) in a given region"""
    lookup_field = 'uuid'
    queryset = models.FineMappedSignal.objects.select_related('analysis')
    serializer_class = serializers.MergedSignalRegionSerializer

    def get_object(self):
        signal = super(FinemappedSignalSummRegionView, self).get_object()
        chrom, start, end = self._query_params()

        # Two files need to be joined
        marg_fn = os.path.join(settings.MEDIA_ROOT, signal.analysis.summary_stats.name)
        cond_fn = os.path.join(settings.MEDIA_ROOT, signal.cond_analysis.name)

        if not os.path.isfile(marg_fn):
            raise drf_exceptions.NotFound(f"Could not find marginal analysis file for uuid {signal.uuid}")

        if not os.path.isfile(cond_fn):
            raise drf_exceptions.NotFound(f"Could not find conditional analysis file for uuid {signal.uuid}")

        marg_reader = guess_gwas_standard(marg_fn)\
            .add_filter('neg_log_pvalue')

        cond_reader = guess_gwas_standard(cond_fn) \
            .add_filter('neg_log_pvalue')

        try:
            marg_records = marg_reader.fetch(chrom, start, end)
        except ValueError:
            # PySAM will throw a ValueError when tabixing to a chrom not present in the file (but it's ok with an
            #   empty region in a known chromosome)
            # Let's make the behavior the same: no known chromosome = no data for region
            marg_records = []

        try:
            cond_records = cond_reader.fetch(chrom, start, end)
        except ValueError:
            # PySAM will throw a ValueError when tabixing to a chrom not present in the file (but it's ok with an
            #   empty region in a known chromosome)
            # Let's make the behavior the same: no known chromosome = no data for region
            cond_records = []

        # We want to produce a joined set of records across two aligned iterators.
        joined = util.merge_variants_in_region(marg_records, cond_records)

        return list(joined)


class LDPairsRegionView(TabixRegionView):
    lookup_field = 'uuid'
    queryset = models.LDStats.objects.all()
    serializer_class = serializers.LDRegionSerializer

    def _query_params_variant(self) -> ty.Tuple[str, int, int, str]:
        """
        All region params, plus:
        - variant should be chr:pos_ref/alt (though we don't validate this b/c not a public API)
        """
        chrom, start, end = super(LDPairsRegionView, self)._query_params()
        params = self.request.query_params

        variant = params.get('variant', None)
        if not variant:
            raise drf_exceptions.ParseError('Must specify reference variant as ""variant=chr:pos_ref/alt"')
        return chrom, start, end, variant

    def get_object(self):
        panel = super(LDPairsRegionView, self).get_object()  # External-facing GWAS id given as slug in url
        chrom, start, end, variant = self._query_params_variant()

        filename = os.path.join(settings.MEDIA_ROOT, panel.ld_data.name)

        if not os.path.isfile(filename):
            # FIXME: If LD panel is re-ingested, deduplication behavior may cause the index to have a hash appended
            #   that doesn't match the gz file
            raise drf_exceptions.NotFound

        # LD files might specify more than one reference variant.
        reader = TabixReader(filename, parser=parsers.parse_plink)\
            .add_filter('snp_a', variant)

        try:
            return list(reader.fetch(chrom, start, end))
        except ValueError:
            # PySAM will throw a ValueError when tabixing to a chrom not present in the file (but it's ok with an
            #   empty region in a known chromosome)
            # Let's make the behavior the same: no known chromosome = no data for region
            return []
