import os
import typing as ty
from typing import Union
from django.db.models import Case, When, Value, IntegerField, BooleanField, Q, F
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import exceptions as drf_exceptions
from rest_framework import serializers as drf_serializers
from rest_framework import generics
from rest_framework.views import APIView
from zorp.readers import TabixReader
from zorp.sniffers import guess_gwas_standard

from colocus.core import models
from colocus.utils.paginators import LargeResultsSetPagination
from colocus.utils.variants import parse_variant
from colocus.core.constants import ANALYSIS_TYPES

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


def annotate_prioritized_signals(queryset, analysis_type_priority=None):
    """
    Annotate a ColocResult queryset with fields indicating which signal should be used
    based on analysis_type_priority.

    Args:
        queryset: ColocResult queryset
        analysis_type_priority: Comma-separated string like "GWAS,eQTL"

    Returns:
        Annotated queryset with 'use_signal1_as_primary' boolean field
    """
    if analysis_type_priority:
        order_list = analysis_type_priority.split(",")

        # Create CASE statements for order1 and order2
        order1_whens = [
            When(signal1__analysis__analysis_type=atype, then=Value(idx))
            for idx, atype in enumerate(order_list)
        ]

        order2_whens = [
            When(signal2__analysis__analysis_type=atype, then=Value(idx))
            for idx, atype in enumerate(order_list)
        ]

        queryset = queryset.annotate(
            order1=Case(
                *order1_whens,
                default=Value(None, output_field=IntegerField()),
                output_field=IntegerField()
            ),
            order2=Case(
                *order2_whens,
                default=Value(None, output_field=IntegerField()),
                output_field=IntegerField()
            )
        )

        # Now determine which signal to use as primary (first signal shown)
        # Logic:
        # - If both None: use signal1
        # - If only one has a value:
        #   - If that value is 0: use that signal
        #   - If that value is 1: use the other signal
        # - If both have values: use the one with lower index

        queryset = queryset.annotate(
            use_signal1_as_primary=Case(
                When(Q(order1__isnull=True) & Q(order2__isnull=True), then=Value(True)),

                When(
                    Q(order1__isnull=False) & Q(order2__isnull=True),
                    then=Case(
                        When(order1=0, then=Value(True)),
                        When(order1=1, then=Value(False)),
                        default=Value(True),
                        output_field=BooleanField()
                    )
                ),

                When(
                    Q(order1__isnull=True) & Q(order2__isnull=False),
                    then=Case(
                        When(order2=0, then=Value(False)),
                        When(order2=1, then=Value(True)),
                        default=Value(True),
                        output_field=BooleanField()
                    )
                ),

                When(
                    Q(order1__isnull=False) & Q(order2__isnull=False),
                    then=Case(
                        When(order1__lt=F('order2'), then=Value(True)),
                        When(order1__gt=F('order2'), then=Value(False)),
                        When(order1=F('order2'), then=Value(True)),
                        output_field=BooleanField()
                    )
                ),

                default=Value(True),
                output_field=BooleanField()
            )
        )
    else:
        queryset = queryset.annotate(
            use_signal1_as_primary=Value(True, output_field=BooleanField())
        )

    return queryset


class ColocResultQueryParamsSerializer(drf_serializers.Serializer):
    include_orphans = drf_serializers.BooleanField(required=False, default=False)
    analysis_type_priority = drf_serializers.CharField(
        required=False, 
        allow_blank=True,
        help_text=(
            'Comma-separated list of analysis types to prioritize when assigning signals. '
            'Example: "eQTL,GWAS" prioritizes eQTL as signal1.'
        )
    )

    def validate_analysis_type_priority(self, value):
        if value:
            # Could add validation here, e.g., check valid analysis types
            types = [t.strip() for t in value.split(',')]
            for t in types:
                if t not in dict(ANALYSIS_TYPES):
                    raise drf_serializers.ValidationError(f"Invalid analysis type: {t}")
        return value

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
        OpenApiParameter(
            name='analysis_type_priority',
            description=(
                'Comma-separated list of analysis types to prioritize when assigning signals to signal1 and signal2. '
                'For example: "eQTL,GWAS" will prioritize eQTL signals as signal1 and GWAS signals as signal2. '
                'Analysis types earlier in the list have higher priority.'
            ),
            required=False,
            type=str
        ),
        OpenApiParameter(
            name='include_orphans',
            description='Include colocalization results where one signal has no other colocalizations',
            required=False,
            type=bool,
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
@method_decorator(cache_page(None), name='get')
class ColocResultListView(generics.ListAPIView):
    """
    ## List colocalization results

    This endpoint provides a list of `ColocResult`. Each result represents one colocalization result, which is
    the result of colocalizing two fine-mapped signals from a GWAS or eQTL analysis.
    """

    def get_queryset(self):
        fields = (
            'signal1', 'signal2',
            'signal1__analysis', 'signal2__analysis',
            'signal1__analysis__trait', 'signal2__analysis__trait',
            'signal1__lead_variant', 'signal2__lead_variant',
            'signal1__analysis__trait__gene', 'signal2__analysis__trait__gene',
            'signal1__analysis__trait__exon', 'signal2__analysis__trait__exon',
            'signal1__analysis__trait__phenotype', 'signal2__analysis__trait__phenotype',
            'signal1__analysis__study', 'signal2__analysis__study',
            'signal1__analysis__publication', 'signal2__analysis__publication',
            'signal1__analysis__dataset', 'signal2__analysis__dataset',
            'signal1__analysis__ld', 'signal2__analysis__ld'
        )

        query_serializer = ColocResultQueryParamsSerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)

        include_orphans = query_serializer.validated_data.get('include_orphans', False)
        analysis_type_priority = query_serializer.validated_data.get('analysis_type_priority')

        if include_orphans:
            queryset = models.ColocResultWithOrphans.objects.select_related(*fields)
        else:
            queryset = models.ColocResult.objects.select_related(*fields)

        queryset = annotate_prioritized_signals(queryset, analysis_type_priority)

        return queryset

    serializer_class = serializers.ColocResultSerializer
    # filterset_class = filters.ColocResultWithOrphansFilter

    @property
    def filterset_class(self):
        query_serializer = ColocResultQueryParamsSerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)

        include_orphans = query_serializer.validated_data.get('include_orphans', False)

        if include_orphans:
            return filters.ColocResultWithOrphansFilter

        return filters.ColocResultFilter


@method_decorator(cache_page(None), name='get')
class ColocResultDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    def get_queryset(self):
        fields = (
            'signal1', 'signal2',
            'signal1__analysis', 'signal2__analysis',
            'signal1__analysis__trait', 'signal2__analysis__trait',
            'signal1__lead_variant', 'signal2__lead_variant',
            'signal1__analysis__trait__gene', 'signal2__analysis__trait__gene',
            'signal1__analysis__trait__exon', 'signal2__analysis__trait__exon',
            'signal1__analysis__trait__phenotype', 'signal2__analysis__trait__phenotype',
            'signal1__analysis__study', 'signal2__analysis__study',
            'signal1__analysis__publication', 'signal2__analysis__publication',
            'signal1__analysis__dataset', 'signal2__analysis__dataset',
            'signal1__analysis__ld', 'signal2__analysis__ld'
        )

        query_serializer = ColocResultQueryParamsSerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)

        include_orphans = query_serializer.validated_data.get('include_orphans', False)
        analysis_type_priority = query_serializer.validated_data.get('analysis_type_priority')

        if include_orphans:
            queryset = models.ColocResultWithOrphans.objects.select_related(*fields)
        else:
            queryset = models.ColocResult.objects.select_related(*fields)

        queryset = annotate_prioritized_signals(queryset, analysis_type_priority)

        return queryset

    serializer_class = serializers.ColocResultSerializer


@method_decorator(cache_page(None), name='dispatch')
class ColocResultSlimListView(APIView):
    """
    API endpoint to return a fast and slimmed-down version of all colocalization results with pagination and caching.
    """
    schema = None # hide from auto-generated docs # noqa

    def get(self, request, *args, **kwargs):
        fields = """
                uuid
                signal1__uuid
                signal1__analysis__uuid
                signal1__analysis__analysis_type
                signal1__analysis__trait__uuid
                signal1__analysis__dataset__uuid
                signal1__analysis__tissue
                signal1__analysis__cell_type
                signal1__analysis__study__uuid
                signal1__lead_variant__vid
                signal2__uuid
                signal2__analysis__uuid
                signal2__analysis__analysis_type
                signal2__analysis__trait__uuid
                signal2__analysis__dataset__uuid
                signal2__analysis__tissue
                signal2__analysis__cell_type
                signal2__analysis__study__uuid
                signal2__lead_variant__vid
                coloc_h4
                r2
            """.split()

        # Change objects into JSON response
        objects = models.ColocResult.objects.values(*fields)
        result = []
        for obj in objects:
            result.append({
                "uuid": obj.get("uuid"),
                "signal1": {
                    "uuid": obj.get("signal1__uuid"),
                    "analysis": {
                        "uuid": obj.get("signal1__analysis__uuid"),
                        "dataset": {
                            "uuid": obj.get("signal1__analysis__dataset__uuid"),
                        },
                        "analysis_type": obj.get("signal1__analysis__analysis_type"),
                        "trait": {
                            "uuid": obj.get("signal1__analysis__trait__uuid"),
                        },
                        "tissue": obj.get("signal1__analysis__tissue"),
                        "cell_type": obj.get("signal1__analysis__cell_type"),
                        "study": {
                            "uuid": obj.get("signal1__analysis__study__uuid"),
                        }
                    },
                    "lead_variant": {
                        "vid": obj.get("signal1__lead_variant__vid")
                    }
                },
                "signal2": {
                    "uuid": obj.get("signal2__uuid"),
                    "analysis": {
                        "uuid": obj.get("signal2__analysis__uuid"),
                        "dataset": {
                            "uuid": obj.get("signal2__analysis__dataset__uuid"),
                        },
                        "analysis_type": obj.get("signal2__analysis__analysis_type"),
                        "trait": {
                            "uuid": obj.get("signal2__analysis__trait__uuid"),
                        },
                        "tissue": obj.get("signal2__analysis__tissue"),
                        "cell_type": obj.get("signal2__analysis__cell_type"),
                        "study": {
                            "uuid": obj.get("signal2__analysis__study__uuid"),
                        }
                    },
                    "lead_variant": {
                        "vid": obj.get("signal2__lead_variant__vid")
                    }
                },
                "coloc_h4": float(format(obj.get("coloc_h4"), '.3g')),
                "r2": float(format(obj.get("r2"), '.3g')) if obj.get("r2") else None,
            })

        # Apply pagination
        paginator = LargeResultsSetPagination()
        paginated_result = paginator.paginate_queryset(result, request)

        # Return paginated response
        return paginator.get_paginated_response(paginated_result)


class LDStatsListView(generics.ListAPIView):
    ordering = ('panel', 'population')
    queryset = models.LDStats.objects.all()
    serializer_class = serializers.LDStatsSerializer


class LDStatsDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.LDStats.objects.all()
    serializer_class = serializers.LDStatsSerializer


@method_decorator(cache_page(None), name='get')
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
    queryset = models.FineMappedSignal.objects.select_related(
        'analysis', 'analysis__trait', 'analysis__trait__gene', 'analysis__trait__exon', 'analysis__study',
        'analysis__ld', 'analysis__dataset', 'analysis__publication', 'analysis__trait__phenotype',
        'lead_variant')
    serializer_class = serializers.FinemappedSignalSerializer
    filterset_class = filters.FinemappedSignalResultFilter


@method_decorator(cache_page(None), name='get')
class FinemappedSignalDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.FineMappedSignal.objects.select_related(
        'analysis', 'analysis__trait', 'analysis__study', 'analysis__ld', 'analysis__dataset',
        'analysis__trait__phenotype', 'analysis__publication', 'lead_variant')
    serializer_class = serializers.FinemappedSignalSerializer


@method_decorator(cache_page(None), name='dispatch')
class FinemappedSignalSlimListView(APIView):
    """
    API endpoint to return a fast and slimmed-down version of all signals with pagination.
    """
    schema = None # hide from auto-generated docs # noqa

    def get(self, request, *args, **kwargs):
        # Define fields
        fields = """
            uuid
            analysis__uuid
            analysis__analysis_type
            analysis__trait__uuid
            analysis__dataset__uuid
            analysis__tissue
            analysis__cell_type
            analysis__study__uuid
            lead_variant__vid
        """.split()

        # Fetch objects
        objects = models.FineMappedSignal.objects.values(*fields)

        # Transform objects
        result = []
        for obj in objects:
            result.append({
                "uuid": obj.get("uuid"),
                "analysis": {
                    "uuid": obj.get("analysis__uuid"),
                    "dataset": {
                        "uuid": obj.get("analysis__dataset__uuid"),
                    },
                    "analysis_type": obj.get("analysis__analysis_type"),
                    "trait": {
                        "uuid": obj.get("analysis__trait__uuid"),
                    },
                    "tissue": obj.get("analysis__tissue"),
                    "cell_type": obj.get("analysis__cell_type"),
                    "study": {
                        "uuid": obj.get("analysis__study__uuid"),
                    }
                },
                "lead_variant": {
                    "vid": obj.get("lead_variant__vid")
                }
            })

        # Apply pagination
        paginator = LargeResultsSetPagination()
        paginated_result = paginator.paginate_queryset(result, request)

        # Return paginated response
        return paginator.get_paginated_response(paginated_result)


@method_decorator(cache_page(None), name='get')
class DataSubmissionListView(generics.ListAPIView):
    """
    ## List of data submissions

    Each data submission is a collection of datasets & analyses that were submitted together. This would be for example
    a set of QTL analyses and GWAS analyses that were submitted together along with their fine-mapping and
    colocalization results.
    """

    ordering = ('uuid',)
    queryset = models.DataSubmission.objects.prefetch_related('publication')
    serializer_class = serializers.DataSubmissionSerializer


@method_decorator(cache_page(None), name='get')
class DataSubmissionDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.DataSubmission.objects.prefetch_related('publication')
    serializer_class = serializers.DataSubmissionDetailSerializer


@method_decorator(cache_page(None), name='get')
class DatasetListView(generics.ListAPIView):
    """
    ## List of datasets

    Each dataset is a collection of analyses that were conducted together. This is typically 1 trait, in the case of a
    GWAS, or thousands of traits, in the case of QTLs.
    """

    ordering = ('uuid',)
    queryset = (models.Dataset.objects
                .select_related('publication', 'submitter')
                .prefetch_related('analysts', 'principal_investigators'))
    serializer_class = serializers.DatasetSerializer


@method_decorator(cache_page(None), name='get')
class DatasetDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = (models.Dataset.objects
                .select_related('publication', 'submitter')
                .prefetch_related('analysts', 'principal_investigators', 'marginal_analyses')
                )
    serializer_class = serializers.DatasetDetailSerializer


@method_decorator(cache_page(None), name='get')
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
        'dataset', 'trait', 'trait__gene', 'trait__exon', 'trait__phenotype', 'study', 'publication', 'ld')
    serializer_class = serializers.MarginalAnalysisSerializer


@method_decorator(cache_page(None), name='get')
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
@method_decorator(cache_page(None), name='get')
class FinemappedSignalSummRegionView(TabixRegionView):
    """Provide all summary stats associated with a particular signal (marginal + conditional) in a given region"""
    lookup_field = 'uuid'
    queryset = models.FineMappedSignal.objects.select_related('analysis')
    serializer_class = serializers.MergedSignalRegionSerializer

    def get_object(self):
        signal = super(FinemappedSignalSummRegionView, self).get_object()
        chrom, start, end = self._query_params()

        # Two files need to be joined
        marg_fn = signal.analysis.summary_stats
        cond_fn = signal.cond_analysis

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


@method_decorator(cache_page(None), name='get')
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
        vchrom, vpos, vref, valt, *rest = parse_variant(variant)
        vpos = int(vpos)

        filename = panel.ld_data

        if not os.path.isfile(filename):
            # FIXME: If LD panel is re-ingested, deduplication behavior may cause the index to have a hash appended
            #   that doesn't match the gz file
            raise drf_exceptions.NotFound

        # LD files might specify more than one reference variant.
        reader = TabixReader(filename, parser=parsers.parse_plink) \
            .add_filter('snp_a', variant) \
            .add_filter('chr_b', chrom) \
            # this does not work even though the library doc says it should # noqa
            # .add_filter('pos_b', lambda x: start <= x <= end) # noqa

        try:
            results = []
            # This pulls out all records that match the reference variant
            for rec in reader.fetch(chrom, vpos - 1, vpos):
                # This restricts to only those variants within the requested region
                if (rec.bp_b >= start) and (rec.bp_b <= end):
                    results.append(rec)

            return results
        except ValueError:
            # PySAM will throw a ValueError when tabixing to a chrom not present in the file (but it's ok with an
            #   empty region in a known chromosome)
            # Let's make the behavior the same: no known chromosome = no data for region
            return []
