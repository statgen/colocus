from rest_framework import serializers as drf_serializers
from rest_framework.reverse import reverse

from colocus.core import models

from .util import serialize_neg_log_pvalue


class StudyHyperlinkRelatedField(drf_serializers.HyperlinkedRelatedField):
    """
    For URLs with two lookup fields (study uuid and pk), we need a custom relationship field serializer.
        (the default hyperlinked serializer doesn't handle nested relationships well)

    See: https://www.django-rest-framework.org/api-guide/relations/#custom-hyperlinked-fields
    """

    def get_url(self, obj, view_name, request, format):
        url_kwargs = {
            'analysis_uuid': obj.analysis.uuid,
            'uuid': obj.uuid
        }
        return reverse(view_name, kwargs=url_kwargs, request=request, format=format)

    def get_object(self, view_name, view_args, view_kwargs):
        lookup_kwargs = {
            'analysis_uuid': view_kwargs['analysis_uuid'],
            'uuid': self.lookup_field,
        }
        return self.get_queryset().get(**lookup_kwargs)


class AnalysisGroupSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = models.AnalysisGroup
        fields = ('uuid', 'study_name', 'study_date', 'authors', 'contact_email', 'pmid', 'label')


class AnalyisGroupDetailSerializer(drf_serializers.ModelSerializer):
    """
    A specialized serializer for when the only thing we are displaying is analysis group.
        This allows more expensive queries (like trait_count`) than the "general purpose" `AnalysisGroupSerializer`,
        which is intended to be embedded inside other things.
    """

    class Meta:
        model = models.AnalysisGroup
        fields = ('uuid', 'study_name', 'study_date', 'authors', 'contact_email', 'pmid', 'trait_count', 'label')


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
    """
    Full set of marginal trait fields for standalone endpoints. Analysis info is embedded into the response because
        the primary use case for this serializer/endpoint is to render pages with all the info we want about this trait.
    """
    analysis = AnalysisGroupSerializer(read_only=True)
    ld = StudyHyperlinkRelatedField(read_only=True, view_name='api:ld-region', lookup_field='uuid')

    class Meta:
        model = models.MarginalTrait
        fields = (
            'uuid', 'analysis',
            'trait_type', 'genome_build', 'metadata', 'ld',
            'study_name', 'label', 'pmid', 'authors', 'external_link',
        )


class MarginalTraitSerializerBrief(drf_serializers.ModelSerializer):
    """
    Serialize a selection of marginal trait fields. Suitable for embedding concise information in another response
    """
    ld = StudyHyperlinkRelatedField(read_only=True, view_name='api:ld-region', lookup_field='uuid')

    class Meta:
        model = models.MarginalTrait
        fields = ('uuid', 'label', 'trait_type', 'genome_build', 'metadata', 'ld', 'study_name')


class MarginalSignalSerializer(drf_serializers.ModelSerializer):
    # TODO: Add link fields to traits
    # Embed the related data into this response to avoid a separate query
    trait = MarginalTraitSerializerBrief(read_only=True)

    lead_variant_neg_log_p = drf_serializers.SerializerMethodField(method_name='get_lead_variant_neg_log_p',
                                                                   read_only=True)

    def get_lead_variant_neg_log_p(self, obj):
        return serialize_neg_log_pvalue(obj.lead_variant_neg_log_p)

    class Meta:
        model = models.MarginalSignal
        fields = (
            'uuid',
            'trait',
            'lead_variant_chrom',
            'lead_variant_pos',
            'lead_variant_marker',
            'lead_variant_neg_log_p',
            'lead_variant_effect',
            'lead_variant_effect_marg',
            'lead_variant_nearest_gene',
            'lead_variant_assoc_gene',
            'lead_variant_assoc_gene_ensg',
            'cond_minp_variant'
        )


class MergedSignalRegionSerializer(drf_serializers.Serializer):
    """
    A generic serializer for when we want to fetch two merged signals in a single request, like trait1-trait2
        (locuscompare plot) or marginal signal + conditional analysis results.
    """
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
        return serialize_neg_log_pvalue(row.t1_neg_log_pvalue)

    def get_t2_neg_log_pvalue(self, row):
        return serialize_neg_log_pvalue(row.t2_neg_log_pvalue)


class ColocResultSerializer(drf_serializers.ModelSerializer):
    analysis = AnalysisGroupSerializer(read_only=True)
    signal1 = MarginalSignalSerializer(read_only=True)
    signal2 = MarginalSignalSerializer(read_only=True)

    class Meta:
        model = models.ColocResult
        fields = ('uuid', 'analysis', 'signal1', 'signal2', 'coloc_h3', 'coloc_h4', 'cross_signal',
                  'r2', 'n_coloc_between_traits', 'marg_cond_flip')
