"""
Filters

https://django-filter.readthedocs.io/en/stable/ref/filterset.html#fields
"""

from django_filters.rest_framework import FilterSet

from colocus.core import models


class ColocResultFilter(FilterSet):
    """
    Default filtering behavior for coloc results.

    Example query: "within a single batch of results, find me all nearby signals for a given trait pair,
      sorted by strongest coloc result first"

      We allow filters to be applied for either signal 1 (usually a GWAS) or signal 2 (some sort of QTL), because
        people might have a particular interest in the line of biological evidence
    """
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
            'coloc_h4': ['gte']  # "query just the significant results"
        }
