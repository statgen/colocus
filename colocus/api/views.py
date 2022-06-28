import os
import typing as ty

from django.conf import settings
from rest_framework import generics
from rest_framework import exceptions as drf_exceptions
from zorp.readers import TabixReader


from colocus.core import models

from . import parsers, serializers


class ColocResultListView(generics.ListAPIView):
    ordering = ('coloc_h4',)
    queryset = models.ColocResult.objects.select_related('analysis', 'signal1', 'signal2')

    serializer_class = serializers.ColocResultSerializer


class ColocResultDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.ColocResult.objects.select_related('analysis', 'signal1', 'signal2')
    serializer_class = serializers.ColocResultSerializer


class MarginalSignalListView(generics.ListAPIView):
    ordering = ('lead_variant_neg_log_p',)
    queryset = models.MarginalSignal.objects.select_related('trait')

    serializer_class = serializers.MarginalSignalSerializer


class MarginalSignalDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.MarginalSignal.objects.select_related('trait')
    serializer_class = serializers.MarginalSignalSerializer


class MarginalSignalSummStatsView(generics.RetrieveAPIView):
    # FIXME: Implement
    pass


class LDPairsListView(generics.ListAPIView):
    ordering = ('panel', 'population')
    queryset = models.LDPairs.objects.all()

    serializer_class = serializers.LDPairsSerializer


class LDPairsDetailView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.LDPairs.objects.all()
    serializer_class = serializers.LDPairsSerializer


class LDPairsRegionView(generics.RetrieveAPIView):
    lookup_field = 'uuid'
    queryset = models.LDPairs.objects.all()
    serializer_class = serializers.LDRegionSerializer

    def get_serializer(self, *args, **kwargs):
        """Unique scenario: a single model that returns a list of records"""
        return super(LDPairsRegionView, self).get_serializer(*args, many=True, **kwargs)

    def get_object(self):
        panel = super(LDPairsRegionView, self).get_object()  # External-facing GWAS id given as slug in url
        chrom, start, end, variant = self._query_params()

        filename = os.path.join(settings.MEDIA_ROOT, panel.ld_data.name)

        if not os.path.isfile(filename):
            # FIXME: If LD panel is re-ingested, deuplication behavior may cause the index to have a hash appended that doesn't match the gz file
            raise drf_exceptions.NotFound

        print('variant', variant)
        reader = TabixReader(filename, parser=parsers.parse_plink)\
            .add_filter('snp_a', variant)

        try:
            return list(reader.fetch(chrom, start, end))
        except ValueError:
            # PySAM will throw a ValueError when tabixing to a chrom not present in the file (but it's ok with an
            #   empty region in a known chromosome)
            # Let's make the behavior the same: no known chromosome = no data for region
            return []

    def _query_params(self) -> ty.Tuple[str, int, int, str]:
        """
        Specific rules for GWAS retrieval
        - Must specify chrom, start, end, and variant as query params
        - start and end must be integers
        - end > start
        - 0 <= (end - start) <= 500000
        - variant should be chr:pos_ref/alt (though we don't validate this b/c not a public API)
        """
        params = self.request.query_params

        chrom = params.get('chrom', None)
        start = params.get('start', None)
        end = params.get('end', None)

        if not (chrom and start and end):
            raise drf_exceptions.ParseError('Must specify "chrom", "start", and "end" as query parameters')

        try:
            start = int(start)
            end = int(end)
        except ValueError:
            raise drf_exceptions.ParseError('"start" and "end" must be integers')

        if end <= start:
            raise drf_exceptions.ParseError('"end" position must be greater than "start"')

        if not (0 <= (end - start) <= settings.LZ_MAX_REGION_SIZE):
            raise drf_exceptions.ParseError(
                f'Cannot handle requested region size. Max allowed is {settings.LZ_MAX_REGION_SIZE}')

        # TODO refactor to base mixin/ super call
        variant = params.get('variant', None)
        if not variant:
            raise drf_exceptions.ParseError('Must specify reference variant as "chr:pos_ref/alt"')
        return chrom, start, end, variant

