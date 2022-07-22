"""
Filters

https://django-filter.readthedocs.io/en/stable/ref/filterset.html#fields
"""

import django_filters

from colocus.core import models


class ColocResultFilter(django_filters.FilterSet):
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
            'analysis': ['exact'],
            'signal1__trait__uuid': ['exact'],
            'signal2__trait__uuid': ['exact'],
            'signal1__lead_variant_pos': ['exact', 'gte', 'gt', 'lte', 'lt'],
            'signal1__lead_variant_nearest_gene': ['exact'],
            'signal2__lead_variant_pos': ['exact', 'gte', 'gt', 'lte', 'lt'],
            'signal2__lead_variant_nearest_gene': ['exact'],
        }
