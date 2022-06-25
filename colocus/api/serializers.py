from rest_framework import serializers as drf_serializers

from colocus.core import models


class AnalyisGroup(drf_serializers.ModelSerializer):
    class Meta:
        model = models.AnalysisGroup
        fields = ('uuid', 'study_name', 'study_date', 'authors', 'contact_email', 'pmid')


class LDPairsSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = models.LDPairs
        fields = ('uuid', 'panel', 'population', 'genome_build')


class MarginalTraitSerializer(drf_serializers.ModelSerializer):
    ld = drf_serializers.HyperlinkedRelatedField(read_only=True, view_name='api:ld-region', lookup_field='uuid')

    class Meta:
        model = models.MarginalTrait
        fields = ('uuid', 'trait_type', 'genome_build', 'metadata', 'ld')


class MarginalSignalSerializer(drf_serializers.ModelSerializer):
    # TODO: Add link fields to traits
    trait = MarginalTraitSerializer(read_only=True)

    class Meta:
        model = models.MarginalSignal
        fields = ('uuid', 'trait', 'lead_variant_chrom', 'lead_variant_pos', 'lead_variant_marker', 'lead_variant_neg_log_p', 'lead_variant_nearest_gene')


class ColocResultSerializer(drf_serializers.ModelSerializer):
    analysis = AnalyisGroup(read_only=True)
    signal1 = MarginalSignalSerializer(read_only=True)
    signal2 = MarginalSignalSerializer(read_only=True)

    class Meta:
        model = models.ColocResult
        fields = ('uuid', 'analysis', 'signal1', 'signal2', 'coloc_h3', 'coloc_h4')
