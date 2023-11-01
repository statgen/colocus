"""
Filters

https://django-filter.readthedocs.io/en/stable/ref/filterset.html#fields
"""

from django.db.models import Q
from django_filters.rest_framework import CharFilter, FilterSet

from colocus.core import models


class ColocResultFilter(FilterSet):
    """
    Default filtering behavior for coloc results.

    Example query: "within a single batch of results, find me all nearby signals for a given trait pair,
      sorted by strongest coloc result first"

      We allow filters to be applied for either signal 1 (usually a GWAS) or signal 2 (some sort of QTL), because
        people might have a particular interest in the line of biological evidence
    """

    # Create an `all_genes` filter that searches all available gene fields
    genes = CharFilter(method='gene_or')

    def gene_or(self, queryset, name, value):
        if "," in value:
            value = value.split(",")
        else:
            value = [value]

        query = Q(signal1__lead_variant_nearest_gene__in=value)
        query |= Q(signal1__lead_variant_assoc_gene__in=value)
        query |= Q(signal1__lead_variant_assoc_gene_ensg__in=value)
        query |= Q(signal2__lead_variant_nearest_gene__in=value)
        query |= Q(signal2__lead_variant_assoc_gene__in=value)
        query |= Q(signal2__lead_variant_assoc_gene_ensg__in=value)

        return queryset.filter(query)

    phenotypes = CharFilter(method='phenotype_or')

    def phenotype_or(self, queryset, name, value):
        if "," in value:
            value = value.split(",")
        else:
            value = [value]

        query = Q(signal1__trait__metadata__trait__in=value)
        query |= Q(signal2__trait__metadata__trait__in=value)

        return queryset.filter(query)

    tissues = CharFilter(method='tissue_or')

    def tissue_or(self, queryset, name, value):
        if "," in value:
            value = value.split(",")
        else:
            value = [value]

        query = Q(signal1__trait__metadata__tissue__in=value)
        query |= Q(signal2__trait__metadata__tissue__in=value)

        return queryset.filter(query)

    trait_uuid = CharFilter(method='trait_uuid_or')

    def trait_uuid_or(self, queryset, name, value):
        if "," in value:
            value = value.split(",")

            query = Q(signal1__trait__uuid__in=value)
            query |= Q(signal2__trait__uuid__in=value)
        else:
            query = Q(signal1__trait__uuid=value)
            query |= Q(signal2__trait__uuid=value)

        return queryset.filter(query)

    signals = CharFilter(method='signal_or')

    def signal_or(self, queryset, name, value):
        if "," in value:
            value = value.split(",")

            query = Q(signal1__uuid__in=value)
            query |= Q(signal2__uuid__in=value)
        else:
            query = Q(signal1__uuid=value)
            query |= Q(signal2__uuid=value)

        return queryset.filter(query)

    studies = CharFilter(method='study_or')

    def study_or(self, queryset, name, value):
        if "," in value:
            value = value.split(",")

            query = Q(signal1__trait__study_name__in=value)
            query |= Q(signal2__trait__study_name__in=value)
        else:
            query = Q(signal1__trait__study_name=value)
            query |= Q(signal2__trait__study_name=value)

        return queryset.filter(query)

    class Meta:
        model = models.ColocResult
        fields = {
            # 'analysis__uuid': ['exact'],  # TODO move this one to a URL segment
            'signal1__trait__uuid': ['exact', 'in'],
            'signal2__trait__uuid': ['exact', 'in'],
            'signal1__lead_variant_chrom': ['exact'],
            'signal1__lead_variant_pos': ['exact', 'gte', 'gt', 'lte', 'lt'],
            'signal1__lead_variant_nearest_gene': ['exact', 'in'],
            'signal2__lead_variant_chrom': ['exact'],
            'signal2__lead_variant_pos': ['exact', 'gte', 'gt', 'lte', 'lt'],
            'signal2__lead_variant_nearest_gene': ['exact'],
            'signal2__lead_variant_assoc_gene': ['exact', 'in'],
            'signal1__lead_variant_neg_log_p': ['gte'],
            'signal2__lead_variant_neg_log_p': ['gte'],
            'coloc_h4': ['gte'],  # "query just the significant results"
            'r2': ['gte']
        }
