from collections import OrderedDict

from rest_framework import serializers as drf_serializers

from colocus.core import models

from .util import serialize_neg_log_pvalue


class ReducedPrecisionFloatField(drf_serializers.FloatField):
    def to_representation(self, value):
        s = format(value, '.3g')
        return float(s)


class NonNullModelSerializer(drf_serializers.ModelSerializer):
    def to_representation(self, instance):
        result = super(NonNullModelSerializer, self).to_representation(instance)
        return OrderedDict([(key, result[key]) for key in result if result[key] is not None])


class DataSubmissionSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = models.DataSubmission
        fields = ('uuid', 'authors', 'contact_email', 'pmid', 'description')


class DataSubmissionDetailSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = models.DataSubmission
        fields = ('uuid', 'authors', 'contact_email', 'pmid', 'trait_count', 'description')


class LDStatsSerializer(drf_serializers.ModelSerializer):
    """
    Represents a set of LD statistics for a single population and genome build. For colocus, we require LD between
    the lead variant of each fine-mapped signal, and all other variants in the region.
    """
    class Meta:
        model = models.LDStats
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


class GeneSerializer(drf_serializers.ModelSerializer):
    """
    A gene is a region of the genome that is transcribed into RNA. Genes are represented by Ensembl gene IDs, which are
    stable identifiers from the Ensembl database. Genes are also given a symbol by HGNC, which is a human-readable
    identifier for the gene, e.g. "TCF7L2".
    """
    class Meta:
        model = models.Gene
        fields = ('ens_id', 'symbol', 'chrom', 'start', 'end')


class ExonSerializer(drf_serializers.ModelSerializer):
    """
    An exon is a region of a gene that is transcribed into RNA. Exons are represented by Ensembl exon IDs, or custom IDs
    that begin with the ensembl gene ID and end with the start/end position of the called exon, e.g.
    ENSG00000123456_1000_2000.
    """
    # gene = GeneSerializer(read_only=True)

    class Meta:
        model = models.Exon
        fields = ('ens_id', 'chrom', 'start', 'end')


class PhenotypeSerializer(drf_serializers.ModelSerializer):
    """
    A phenotype is a type of trait. These are usually human diseases or measurements of human traits, such as "BMI" or
    "type 2 diabetes". Phenotypes are represented by EFO IDs, which are stable identifiers from the Experimental
    Factor Ontology (EFO).
    """
    class Meta:
        model = models.Phenotype
        fields = ('efo_id', 'kp_id', 'name')


class TraitSerializer(NonNullModelSerializer):
    """
    A trait is a phenotype or other biological property that has been studied in one or more analyses. This could be a
    phenotype like type 2 diabetes, or a gene expression trait like "expression of gene X".
    """

    gene = GeneSerializer(read_only=True)
    exon = ExonSerializer(read_only=True)
    phenotype = PhenotypeSerializer(read_only=True)

    class Meta:
        model = models.Trait
        fields = ('uuid', 'biomarker_type', 'gene', 'exon', 'phenotype')


class StudySerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = models.Study
        fields = ('uuid', 'description')


class LeadVariantSerializer(drf_serializers.ModelSerializer):
    """
    Helper object for representing the lead variant in a fine-mapped signal.
    """
    class Meta:
        model = models.LeadVariant
        fields = ('vid', 'chrom', 'pos', 'ref', 'alt')


class PublicationSerializer(drf_serializers.ModelSerializer):
    """
    A publication is a scientific paper that describes one or more analyses. Publications have either a PubMed
    ID (stable identifiers from the PubMed database), or a DOI (Digital Object Identifier), or both.
    """
    class Meta:
        model = models.Publication
        fields = ('pmid', 'doi', 'authors', 'title', 'year', 'journal')


class PersonSerializer(drf_serializers.ModelSerializer):
    """
    A person is an individual who contributed to an analysis or dataset. People have names and email addresses.
    """
    class Meta:
        model = models.Person
        fields = ('name', 'orcid', 'institution')


class MarginalAnalysisSerializerBrief(drf_serializers.ModelSerializer):
    """
    A marginal analysis, sometimes shortened to just 'analysis', represents a marginal association scan
    for a single trait. In other words, it is the output of GWAS or eQTL analysis for one trait or gene.
    """

    ld = drf_serializers.CharField(source='ld.uuid', read_only=True)
    trait = TraitSerializer(read_only=True)
    study = StudySerializer(read_only=True)

    class Meta:
        model = models.MarginalAnalysis
        fields = ('uuid', 'analysis_type', 'genome_build', 'trait', 'tissue', 'cell_type', 'description', 'ancestry',
                  'study', 'ld')


class DatasetSerializer(drf_serializers.ModelSerializer):
    """
    A dataset is a collection of analyses that are related in some way. For example, all analyses that were performed
    on a single study or cohort would be grouped into a single dataset.
    """
    publication = PublicationSerializer(read_only=True)
    submitter = PersonSerializer(read_only=True)
    analysts = PersonSerializer(many=True, read_only=True)
    principal_investigators = PersonSerializer(many=True, read_only=True)

    class Meta:
        model = models.Dataset
        fields = ('uuid', 'analysis_type', 'genome_build', 'tissue', 'cell_type', 'ancestry', 'n_traits',
                  'n_traits_with_sig', 'publication', 'external_link', 'submitter', 'analysts',
                  'principal_investigators')


class DatasetDetailSerializer(drf_serializers.ModelSerializer):
    """
    A dataset is a collection of analyses that are related in some way. For example, all analyses that were performed
    on a single study or cohort would be grouped into a single dataset.
    """
    publication = PublicationSerializer(read_only=True)
    submitter = PersonSerializer(read_only=True)
    analysts = PersonSerializer(many=True, read_only=True)
    principal_investigators = PersonSerializer(many=True, read_only=True)
    analysis = drf_serializers.SerializerMethodField()

    class Meta:
        model = models.Dataset
        fields = ('uuid', 'analysis_type', 'genome_build', 'tissue', 'cell_type', 'ancestry', 'n_traits',
                  'n_traits_with_sig', 'publication', 'external_link', 'submitter', 'analysts',
                  'principal_investigators', 'analysis')

    def get_analysis(self, obj):
        count = obj.marginal_analyses.count()
        if count > 1:
            return None
        else:
            return MarginalAnalysisSerializerBrief(obj.marginal_analyses.first()).data


class DatasetSerializerBrief(drf_serializers.ModelSerializer):
    class Meta:
        model = models.Dataset
        fields = ('uuid',)


class MarginalAnalysisSerializer(drf_serializers.ModelSerializer):
    """
    A marginal analysis, sometimes shortened to just 'analysis', represents a marginal association scan
    for a single trait. In other words, it is the output of GWAS or eQTL analysis for one trait or gene.
    """

    dataset = DatasetSerializerBrief(read_only=True)
    trait = TraitSerializer(read_only=True)
    ld = drf_serializers.CharField(source='ld.uuid', read_only=True)
    study = StudySerializer(read_only=True)
    publication = PublicationSerializer(read_only=True)

    class Meta:
        model = models.MarginalAnalysis
        fields = (
            'uuid', 'dataset', 'analysis_type', 'genome_build', 'trait', 'tissue', 'cell_type', 'description',
            'ancestry', 'study', 'publication', 'ld', 'external_link'
        )


class FinemappedSignalSerializer(drf_serializers.ModelSerializer):
    """
    One specific signal after fine-mapping or conditional analysis of a marginal association analysis. Usually this
    process is performed by SuSiE, APEX, FINEMAP, or GCTA.

    Fields:
    - `uuid`: A stable unique identifier for this fine-mapped signal
    - `analysis`: The analysis in which this signal was identified
    - `lead_variant`: The variant with the strongest association in this signal
    - `neg_log_p`: The negative log10 p-value of the lead variant
    - `effect_cond`: The effect size of the lead variant in the conditional analysis
    - `effect_marg`: The effect size of the lead variant in the marginal analysis
    """

    analysis = MarginalAnalysisSerializer(read_only=True)
    lead_variant = LeadVariantSerializer(read_only=True)
    neg_log_p = drf_serializers.SerializerMethodField(
        method_name='get_neg_log_p',
        read_only=True)

    def get_neg_log_p(self, obj):
        return serialize_neg_log_pvalue(obj.neg_log_p)

    class Meta:
        model = models.FineMappedSignal
        fields = (
            'uuid',
            'analysis',
            'lead_variant',
            'neg_log_p',
            'effect_cond',
            'effect_marg',
            'cond_minp_variant',
            'is_marg'
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
    """
    A `ColocResult` represents the output of a colocalization analysis between two signals. It is the result of
    comparing two `FineMappedSignal` objects, and represents the probability that the two signals are both
    associated with the same causal variant.
    """

    signal1 = FinemappedSignalSerializer(read_only=True, label="Signal 1")
    signal2 = FinemappedSignalSerializer(read_only=True, label="Signal 2")
    coloc_h3 = ReducedPrecisionFloatField(read_only=True, label="Posterior probability of H3")
    coloc_h4 = ReducedPrecisionFloatField(read_only=True, label="Posterior probability of H4")
    r2 = ReducedPrecisionFloatField(read_only=True, label="r2 between lead variants")
    n_coloc_between_traits = drf_serializers.IntegerField(
        read_only=True,
        label="Number of coloc results between signal1's trait and signal2's trait")

    class Meta:
        model = models.ColocResult
        fields = ('uuid', 'signal1', 'signal2', 'coloc_h3', 'coloc_h4', 'cross_signal',
                  'r2', 'n_coloc_between_traits', 'marg_cond_flip')
