from rest_framework import generics
from colocus.core import models

from . import serializers


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
    # TODO: Custom tabix file view- this maybe isn't a serializer at all
    pass
