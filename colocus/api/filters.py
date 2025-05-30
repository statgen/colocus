"""
Filters

https://django-filter.readthedocs.io/en/stable/ref/filterset.html#fields
"""

import re

from django.db.models import Q
from django_filters.rest_framework import (
    CharFilter,
    FilterSet,
    NumberFilter,
    OrderingFilter,
)

from colocus.core import models


def parse_region(region):
    regex = r'^(?:chr)?([0-9a-zA-Z]+):(\d+)-(\d+)$'
    match = re.match(regex, region)
    if match:
        return match.groups()


class ColocResultFilter(FilterSet):
    """
    Default filtering behavior for coloc results.

    Example query: "within a single batch of results, find me all nearby signals for a given trait pair,
      sorted by strongest coloc result first"

      We allow filters to be applied for either signal 1 (usually a GWAS) or signal 2 (some sort of QTL), because
        people might have a particular interest in the line of biological evidence
    """
    def create_query(self, field, value):
        if "," in value:
            value = value.split(",")
            query = Q(**{f'{field}__in': value})
        else:
            query = Q(**{f'{field}': value})
        return query

    # Create an `all_genes` filter that searches all available gene fields
    genes = CharFilter(
        method='gene_or',
        label="Provide a list of comma-separated genes to filter by. Can be either Ensembl IDs or gene symbols.")

    def gene_or(self, queryset, name, value):
        query = self.create_query('signal1__analysis__trait__gene__symbol', value)
        query |= self.create_query('signal1__analysis__trait__gene__ens_id', value)
        query |= self.create_query('signal2__analysis__trait__gene__symbol', value)
        query |= self.create_query('signal2__analysis__trait__gene__ens_id', value)
        return queryset.filter(query)

    variants = CharFilter(
        method='variant_or',
        label="Provide a list of comma-separated variant IDs to filter by.")

    def variant_or(self, queryset, name, value):
        query = self.create_query('signal1__lead_variant__vid', value)
        query |= self.create_query('signal2__lead_variant__vid', value)
        return queryset.filter(query)

    traits = CharFilter(
        method='trait_or',
        label="Provide a list of comma-separated traits to filter by.")

    def trait_or(self, queryset, name, value):
        """
        Filter on traits.
        """
        query = self.create_query('signal1__analysis__trait__uuid', value)
        query |= self.create_query('signal2__analysis__trait__uuid', value)
        return queryset.filter(query)

    phenotypes = CharFilter(
        method='phenotype_or',
        label="Provide a list of comma-separated phenotypes to filter by.")

    def phenotype_or(self, queryset, name, value):
        """
        Filter on phenotypes.
        """
        query = self.create_query('signal1__analysis__trait__phenotype__name', value)
        query |= self.create_query('signal2__analysis__trait__phenotype__name', value)
        return queryset.filter(query)

    tissues = CharFilter(
        method='tissue_or',
        label="Provide a list of comma-separated tissues to filter by.")

    def tissue_or(self, queryset, name, value):
        query = self.create_query('signal1__analysis__tissue', value)
        query |= self.create_query('signal2__analysis__tissue', value)
        return queryset.filter(query)

    cell_types = CharFilter(
        method='cell_type_or',
        label="Provide a list of comma-separated cell types to filter by.")

    def cell_type_or(self, queryset, name, value):
        query = self.create_query('signal1__analysis__cell_type', value)
        query |= self.create_query('signal2__analysis__cell_type', value)
        return queryset.filter(query)

    analyses = CharFilter(
        method='analysis_uuid_or',
        label="Provide a list of comma-separated marginal analysis UUIDs to filter by.")

    def analysis_uuid_or(self, queryset, name, value):
        query = self.create_query('signal1__analysis__uuid', value)
        query |= self.create_query('signal2__analysis__uuid', value)
        return queryset.filter(query)

    signals = CharFilter(
        method='signal_or',
        label="Provide a list of comma-separated fine-mapped signal UUIDs to filter by.")

    def signal_or(self, queryset, name, value):
        query = self.create_query('signal1__uuid', value)
        query |= self.create_query('signal2__uuid', value)
        return queryset.filter(query)

    studies = CharFilter(
        method='study_or',
        label="Provide a list of comma-separated study UUIDs to filter by.")

    def study_or(self, queryset, name, value):
        query = self.create_query('signal1__analysis__study__uuid', value)
        query |= self.create_query('signal2__analysis__study__uuid', value)
        return queryset.filter(query)

    def filter_region(self, queryset, name, value):
        """
        Filter results within a specified chromosome & position range.

        The expected format of the input is 'chr:start-end', e.g., '4:10000-20000'.

        :param queryset: The base queryset.
        :param name: The name of the requested filter field in the API, here 'signal1_region' or 'signal2_region'.
        :param value: The value provided for the filter, expected in 'chr:start-end' format.
        :return: A filtered QuerySet.
        """
        match = parse_region(value)

        if match:
            chrom, start_pos, end_pos = match

            pos_field = None
            if "signal1" in name:
                pos_field = "signal1__lead_variant__pos"
            elif "signal2" in name:
                pos_field = "signal2__lead_variant__pos"

            chrom_field = None
            if "signal1" in name:
                chrom_field = "signal1__lead_variant__chrom"
            elif "signal2" in name:
                chrom_field = "signal2__lead_variant__chrom"

            if chrom_field and pos_field:
                return queryset.filter(
                    Q(**{f'{chrom_field}': chrom})
                    & Q(**{f'{pos_field}__gte': start_pos})
                    & Q(**{f'{pos_field}__lte': end_pos})
                )

        return queryset

    signal1_region = CharFilter(
        method='filter_region',
        label="Only retrieve signal 1 results within a specified region given as chr:start-end")

    signal2_region = CharFilter(
        method='filter_region',
        label="Only retrieve signal 2 results within a specified region given as chr:start-end")

    signal1_analysis = CharFilter(field_name='signal1__analysis__uuid', lookup_expr='exact',
                                  label="Signal 1 analysis UUID")
    signal2_analysis = CharFilter(field_name='signal2__analysis__uuid', lookup_expr='exact',
                                  label="Signal 2 analysis UUID")

    signal1_trait = CharFilter(field_name='signal1__analysis__trait__uuid', lookup_expr='exact',
                               label="Signal 1 trait UUID")
    signal2_trait = CharFilter(field_name='signal2__analysis__trait__uuid', lookup_expr='exact',
                               label="Signal 2 trait UUID")

    signal1_min_logp = NumberFilter(field_name='signal1__neg_log_p', lookup_expr='gte',
                                    label="Minimum -log10 p-value for signal 1")
    signal2_min_logp = NumberFilter(field_name='signal2__neg_log_p', lookup_expr='gte',
                                    label="Minimum -log10 p-value for signal 2")

    min_h4 = NumberFilter(field_name='coloc_h4', lookup_expr='gte', label="Minimum PP(H4)")
    min_r2 = NumberFilter(field_name='r2', lookup_expr='gte', label="Minimum r2 between the two signals' lead variants")

    order_by_field = 'ordering'
    ordering = OrderingFilter(
        # fields(('model field name', 'parameter name used by API request / user'),)
        fields=(
            ('coloc_h3', 'h3'),
            ('coloc_h4', 'h4'),
            ('r2', 'r2'),
            ('n_coloc_between_traits', 'n_coloc_between_traits'),
            ('signal1__neg_log_p', 'signal1_logp'),
            ('signal2__neg_log_p', 'signal2_logp'),
            ('signal1__lead_variant__chrom', 'signal1_chrom'),
            ('signal1__lead_variant__pos', 'signal1_pos'),
            ('signal1__analysis__trait__uuid', 'signal1_trait'),
            ('signal2__analysis__trait__uuid', 'signal2_trait'),
            ('signal2__lead_variant__chrom', 'signal2_chrom'),
            ('signal2__lead_variant__pos', 'signal2_pos'),
            ('signal1__analysis__trait__gene__ens_id', 'signal1_gene_ens_id'),
            ('signal1__analysis__trait__gene__symbol', 'signal1_gene_symbol'),
            ('signal1__analysis__tissue', 'signal1_tissue'),
            ('signal1__analysis__cell_type', 'signal1_cell_type'),
            ('signal1__analysis__trait__exon__ens_id', 'signal1_exon_ens_id'),
            ('signal2__analysis__trait__gene__ens_id', 'signal2_gene_ens_id'),
            ('signal2__analysis__trait__gene__symbol', 'signal2_gene_symbol'),
            ('signal2__analysis__tissue', 'signal2_tissue'),
            ('signal2__analysis__cell_type', 'signal2_cell_type'),
            ('signal2__analysis__trait__exon__ens_id', 'signal2_exon_ens_id'),
            ('signal1__analysis__study__uuid', 'signal1_study'),
            ('signal2__analysis__study__uuid', 'signal2_study')
        )
    )

    class Meta:
        model = models.ColocResult
        fields = (
            'uuid',
            'genes',
            'variants',
            'traits',
            'phenotypes',
            'tissues',
            'cell_types',
            'analyses',
            'signals',
            'studies',
            'signal1_trait',
            'signal2_trait',
            'signal1_region',
            'signal2_region',
            'signal1_analysis',
            'signal2_analysis',
            'signal1_min_logp',
            'signal2_min_logp',
            'min_h4',
            'min_r2',
        )
