import math
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
    # Embed the related data into this response to avoid a separate query
    trait = MarginalTraitSerializer(read_only=True)

    class Meta:
        model = models.MarginalSignal
        fields = ('uuid', 'trait', 'lead_variant_chrom', 'lead_variant_pos', 'lead_variant_marker', 'lead_variant_neg_log_p', 'lead_variant_nearest_gene')


class MergedSignalRegionSerializer(drf_serializers.Serializer):
    chromosome = drf_serializers.CharField(source='chrom', read_only=True)
    position = drf_serializers.IntegerField(source='pos', read_only=True)
    ref_allele = drf_serializers.CharField(source='ref', read_only=True)
    alt_allele = drf_serializers.CharField(source='alt', read_only=True)
    variant = drf_serializers.CharField(source='marker', read_only=True)

    t1_neg_log_pvalue = drf_serializers.SerializerMethodField(method_name='get_t1_neg_log_pvalue', read_only=True)
    t1_beta = drf_serializers.FloatField(read_only=True)
    t1_stderr_beta = drf_serializers.FloatField(read_only=True)
    t1_alt_allele_freq = drf_serializers.FloatField(read_only=True)

    t2_neg_log_pvalue = drf_serializers.SerializerMethodField(method_name='get_t2_neg_log_pvalue', read_only=True)
    t2_beta = drf_serializers.FloatField(read_only=True)
    t2_stderr_beta = drf_serializers.FloatField(read_only=True)
    t2_alt_allele_freq = drf_serializers.FloatField(read_only=True)

    def get_t1_neg_log_pvalue(self, row):
        """
        Many GWAS programs suffer from underflow and may represent small p=0/-logp=inf

        The JSON standard can't handle "Infinity", but the string 'Infinity' can be type-coerced by JS, eg +value
        Therefore we serialize this as a special case so it can be used in the frontend
        """
        value = row.t1_neg_log_pvalue
        if value is not None and math.isinf(value):
            return 'Infinity'
        else:
            return value

    def get_t2_neg_log_pvalue(self, row):
        """See t1 above"""
        value = row.t2_neg_log_pvalue
        if value is not None and math.isinf(value):
            return 'Infinity'
        else:
            return value


class ColocResultSerializer(drf_serializers.ModelSerializer):
    analysis = AnalyisGroup(read_only=True)
    signal1 = MarginalSignalSerializer(read_only=True)
    signal2 = MarginalSignalSerializer(read_only=True)

    class Meta:
        model = models.ColocResult
        fields = ('uuid', 'analysis', 'signal1', 'signal2', 'coloc_h3', 'coloc_h4')
