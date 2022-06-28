from rest_framework import serializers as drf_serializers

from colocus.core import models


class AnalyisGroup(drf_serializers.ModelSerializer):
    class Meta:
        model = models.AnalysisGroup
        fields = ('uuid', 'study_name', 'study_date', 'authors', 'contact_email', 'pmid')


class LDPairsSerializer(drf_serializers.ModelSerializer):
    # TODO: It would be nice to include hyperlinks for related fields; DRF fields behavior gets weird
    class Meta:
        model = models.LDPairs
        fields = ('uuid', 'panel', 'population', 'genome_build')


class LDRegionSerializer(drf_serializers.Serializer):
    """Serialize parsed data from a PLINK formatted LD file, with known columns"""
    chromosome1 = drf_serializers.CharField(source='chrom_a', read_only=True)
    position1 = drf_serializers.IntegerField(source='bp_a', read_only=True)
    variant1 = drf_serializers.CharField(source='snp_a', read_only=True)
    chromosome2 = drf_serializers.CharField(source='chrom_b', read_only=True)
    position2 = drf_serializers.IntegerField(source='bp_b', read_only=True)
    variant2 = drf_serializers.CharField(source='snp_b', read_only=True)
    correlation = drf_serializers.FloatField(source='r2', read_only=True)


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
