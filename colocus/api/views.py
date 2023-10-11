import os
import typing as ty
from typing import Union

from django.conf import settings
from rest_framework import exceptions as drf_exceptions
from rest_framework import generics
from zorp.readers import TabixReader
from zorp.sniffers import guess_gwas_standard

from colocus.core import models

from . import filters, parsers, serializers, util


# Base classes shared among views
# --------------------------------
class OneStudyMixin:
    """Most URLs in this app are scoped to one particular study. Restrict the queryset accordingly"""
    def filter_queryset(self, queryset):
        """"""
        queryset = super(OneStudyMixin, self).filter_queryset(queryset)        # type: ignore
        return queryset.filter(analysis__uuid=self.kwargs['analysis_uuid'])    # type: ignore


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


# Metadata endpoints
# -----------------------
class AnalysisGroupListView(generics.ListAPIView):
    ordering = ('study_date',)
    queryset = models.AnalysisGroup.objects.all()
    serializer_class = serializers.AnalyisGroupDetailSerializer


class AnalysisGroupDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.AnalysisGroup.objects.all()
    serializer_class = serializers.AnalyisGroupDetailSerializer


class ColocResultListView(OneStudyMixin, generics.ListAPIView):
    ordering = ('-coloc_h4',)
    queryset = models.ColocResult.objects\
        .select_related('signal1', 'signal2', 'analysis', 'signal1__trait', 'signal2__trait')\
        .prefetch_related('signal1__trait__ld', 'signal2__trait__ld')

    serializer_class = serializers.ColocResultSerializer
    filterset_class = filters.ColocResultFilter
    ordering_fields = (
        'coloc_h4',
        'r2',
        'cross_signal__effect',
        'n_coloc_between_traits',
        'signal1__lead_variant_neg_log_p',
        'signal1__lead_variant_chrom',
        'signal1__lead_variant_pos',
        'signal1__trait__metadata__trait',
        'signal2__lead_variant_neg_log_p',
        'signal2__lead_variant_chrom',
        'signal2__lead_variant_pos',
        'signal2__trait__metadata__gene',
        'signal2__trait__metadata__gene_ensg',
        'signal2__trait__metadata__tissue',
        'signal1__lead_variant_nearest_gene',
        'signal2__lead_variant_assoc_gene',
        'signal1__trait__study_name',
        'signal2__trait__study_name'
    )


class ColocResultDetailView(OneStudyMixin, generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.ColocResult.objects.select_related('analysis', 'signal1', 'signal2')
    serializer_class = serializers.ColocResultSerializer


class LDPairsListView(OneStudyMixin, generics.ListAPIView):
    ordering = ('panel', 'population')
    queryset = models.LDPairs.objects.all()

    serializer_class = serializers.LDPairsSerializer


class LDPairsDetailView(OneStudyMixin, generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.LDPairs.objects.all()
    serializer_class = serializers.LDPairsSerializer


class MarginalSignalListView(OneStudyMixin, generics.ListAPIView):
    ordering = ('lead_variant_neg_log_p',)
    queryset = models.MarginalSignal.objects.select_related('trait').prefetch_related('trait__ld')

    serializer_class = serializers.MarginalSignalSerializer


class MarginalSignalDetailView(OneStudyMixin, generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.MarginalSignal.objects.select_related('trait')
    serializer_class = serializers.MarginalSignalSerializer


class MarginalTraitListView(OneStudyMixin, generics.ListAPIView):
    ordering = ('study_name',)
    queryset = models.MarginalTrait.objects.select_related('analysis').prefetch_related('ld')

    serializer_class = serializers.MarginalTraitSerializer


class MarginalTraitDetailView(OneStudyMixin, generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.MarginalTrait.objects.select_related('analysis')
    serializer_class = serializers.MarginalTraitSerializer


# Tabix-based "region view" endpoints
# -------------------------------------
class MarginalSignalSummRegionView(OneStudyMixin, TabixRegionView):
    """Provide all summary stats associated with a particular signal (marginal + conditional) in a given region"""
    lookup_field = 'uuid'
    queryset = models.MarginalSignal.objects.select_related('trait')
    serializer_class = serializers.MergedSignalRegionSerializer

    def get_object(self):
        signal = super(MarginalSignalSummRegionView, self).get_object()
        chrom, start, end = self._query_params()

        # Two files need to be joined
        marg_fn = os.path.join(settings.MEDIA_ROOT, signal.trait.summary_stats.name)
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
    queryset = models.LDPairs.objects.all()
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
