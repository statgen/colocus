"""
Filters

https://django-filter.readthedocs.io/en/stable/ref/filterset.html#fields
"""

import re

from django.db.models import Case, F, Q, Value, When
from django.db.models.functions import Greatest
from django_filters.rest_framework import (
    CharFilter,
    FilterSet,
    NumberFilter,
    OrderingFilter,
)

from colocus.core import models
from colocus.core.constants import ANALYSIS_TYPES


def parse_region(region):
    regex = r'^(?:chr)?([0-9a-zA-Z]+):(\d+)-(\d+)$'
    match = re.match(regex, region)
    if match:
        return match.groups()


class NullsLastOrderingFilter(OrderingFilter):
    """OrderingFilter that always puts NULL values last."""

    def filter(self, qs, value):
        if value in ([], (), {}, None, ''):
            return qs

        ordering = []
        for param in value:
            descending = param.startswith('-')
            param = param.lstrip('-')

            field_name = self.param_map.get(param, param)

            if descending:
                ordering.append(F(field_name).desc(nulls_last=True))
            else:
                ordering.append(F(field_name).asc(nulls_last=True))

        return qs.order_by(*ordering)


class BaseColocResultFilter(FilterSet):
    """
    Default filtering behavior for coloc results.

    Example query: "within a single batch of results, find me all nearby signals for a given trait pair,
      sorted by strongest coloc result first"

      We allow filters to be applied for either signal 1 (usually a GWAS) or signal 2 (some sort of QTL), because
        people might have a particular interest in the line of biological evidence
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamically create min_logp_{analysis_type} filters
        for _, analysis_type_name in ANALYSIS_TYPES:
            filter_name = f'min_logp_{analysis_type_name.lower()}'     # filter name convention requires min_logp_*
            field_name = f'logp_max_over_{analysis_type_name.lower()}' # field created in filter_queryset

            # Only add if not already defined as a class attribute
            if filter_name not in self.filters:
                self.filters[filter_name] = NumberFilter(
                    field_name=field_name,
                    lookup_expr='gte',
                    label=(
                        f"Minimum -log10 p-value for {analysis_type_name} signals "
                        f"(only colocalizations with at least 1 {analysis_type_name} signal will be returned)"
                    )
                )

    def filter_queryset(self, queryset):
        # Add some fields that are useful for filtering/sorting but not stored directly in the DB
        # Dynamically create logp_max_over_{analysis_type} for each analysis type
        for _, analysis_type_name in ANALYSIS_TYPES:
            field_name = f'logp_max_over_{analysis_type_name.lower()}'
            queryset = queryset.annotate(**{
                field_name: Greatest(
                    Case(
                        When(signal1__analysis__analysis_type=analysis_type_name, then=F('signal1__neg_log_p')),
                        default=Value(float('-inf'))
                    ),
                    Case(
                        When(signal2__analysis__analysis_type=analysis_type_name, then=F('signal2__neg_log_p')),
                        default=Value(float('-inf'))
                    )
                )
            })

            # If the corresponding filter is applied, exclude records with no valid signal of that type
            filter_param = f'min_logp_{analysis_type_name.lower()}'
            if self.data.get(filter_param):
                queryset = queryset.exclude(
                    Q(**{f'{field_name}': float('-inf')}) | Q(**{f'{field_name}__isnull': True})
                )

        # Add conditional annotations for ordering
        # These are necessary because on a per-row basis, signals may be swapped depending on user preference
        # (e.g. analysis_priority), so we need to create consistent "primary" and "secondary" signal fields
        queryset = queryset.annotate(
            primary_signal_trait=Case(
                When(no_signal_swap=True, then=F('signal1__analysis__trait__uuid')),
                default=F('signal2__analysis__trait__uuid')
            ),
            secondary_signal_trait=Case(
                When(no_signal_swap=True, then=F('signal2__analysis__trait__uuid')),
                default=F('signal1__analysis__trait__uuid')
            ),
            primary_signal_chrom=Case(
                When(no_signal_swap=True, then=F('signal1__lead_variant__chrom')),
                default=F('signal2__lead_variant__chrom')
            ),
            secondary_signal_chrom=Case(
                When(no_signal_swap=True, then=F('signal2__lead_variant__chrom')),
                default=F('signal1__lead_variant__chrom')
            ),
            primary_signal_pos=Case(
                When(no_signal_swap=True, then=F('signal1__lead_variant__pos')),
                default=F('signal2__lead_variant__pos')
            ),
            secondary_signal_pos=Case(
                When(no_signal_swap=True, then=F('signal2__lead_variant__pos')),
                default=F('signal1__lead_variant__pos')
            ),
            primary_signal_logp=Case(
                When(no_signal_swap=True, then=F('signal1__neg_log_p')),
                default=F('signal2__neg_log_p')
            ),
            secondary_signal_logp=Case(
                When(no_signal_swap=True, then=F('signal2__neg_log_p')),
                default=F('signal1__neg_log_p')
            ),
            primary_signal_tissue=Case(
                When(no_signal_swap=True, then=F('signal1__analysis__tissue')),
                default=F('signal2__analysis__tissue')
            ),
            secondary_signal_tissue=Case(
                When(no_signal_swap=True, then=F('signal2__analysis__tissue')),
                default=F('signal1__analysis__tissue')
            ),
            primary_signal_cell_type=Case(
                When(no_signal_swap=True, then=F('signal1__analysis__cell_type')),
                default=F('signal2__analysis__cell_type')
            ),
            secondary_signal_cell_type=Case(
                When(no_signal_swap=True, then=F('signal2__analysis__cell_type')),
                default=F('signal1__analysis__cell_type')
            ),
            primary_signal_study=Case(
                When(no_signal_swap=True, then=F('signal1__analysis__study__uuid')),
                default=F('signal2__analysis__study__uuid')
            ),
            secondary_signal_study=Case(
                When(no_signal_swap=True, then=F('signal2__analysis__study__uuid')),
                default=F('signal1__analysis__study__uuid')
            ),
            primary_signal_gene_ens_id=Case(
                When(no_signal_swap=True, then=F('signal1__analysis__trait__gene__ens_id')),
                default=F('signal2__analysis__trait__gene__ens_id')
            ),
            secondary_signal_gene_ens_id=Case(
                When(no_signal_swap=True, then=F('signal2__analysis__trait__gene__ens_id')),
                default=F('signal1__analysis__trait__gene__ens_id')
            ),
            primary_signal_gene_symbol=Case(
                When(no_signal_swap=True, then=F('signal1__analysis__trait__gene__symbol')),
                default=F('signal2__analysis__trait__gene__symbol')
            ),
            secondary_signal_gene_symbol=Case(
                When(no_signal_swap=True, then=F('signal2__analysis__trait__gene__symbol')),
                default=F('signal1__analysis__trait__gene__symbol')
            ),
            primary_signal_exon_ens_id=Case(
                When(no_signal_swap=True, then=F('signal1__analysis__trait__exon__ens_id')),
                default=F('signal2__analysis__trait__exon__ens_id')
            ),
            secondary_signal_exon_ens_id=Case(
                When(no_signal_swap=True, then=F('signal2__analysis__trait__exon__ens_id')),
                default=F('signal1__analysis__trait__exon__ens_id')
            ),
        )

        return super().filter_queryset(queryset)

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

    analysis_types = CharFilter(
        method="analysis_types_or",
        label="Provide a list of comma-separated analysis types to filter by."
    )

    def analysis_types_or(self, queryset, name, value):
        query = self.create_query('signal1__analysis__analysis_type', value)
        query |= self.create_query('signal2__analysis__analysis_type', value)
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

            if "signal1" in name:
                chrom_field = "signal1__lead_variant__chrom"
                pos_field = "signal1__lead_variant__pos"
                return queryset.filter(
                    Q(**{
                      "no_signal_swap": True,
                      f'{chrom_field}': chrom,
                      f'{pos_field}__gte': start_pos,
                      f'{pos_field}__lte': end_pos}) |
                    Q(**{
                      "no_signal_swap": False,
                      f'{chrom_field.replace("signal1", "signal2")}': chrom,
                      f'{pos_field.replace("signal1", "signal2")}__gte': start_pos,
                      f'{pos_field.replace("signal1", "signal2")}__lte': end_pos})
                )
            elif "signal2" in name:
                chrom_field = "signal2__lead_variant__chrom"
                pos_field = "signal2__lead_variant__pos"
                return queryset.filter(
                    Q(**{
                      "no_signal_swap": True,
                      f'{chrom_field}': chrom,
                      f'{pos_field}__gte': start_pos,
                      f'{pos_field}__lte': end_pos}) |
                    Q(**{
                      "no_signal_swap": False,
                      f'{chrom_field.replace("signal2", "signal1")}': chrom,
                      f'{pos_field.replace("signal2", "signal1")}__gte': start_pos,
                      f'{pos_field.replace("signal2", "signal1")}__lte': end_pos})
                )
            else:
                return queryset.filter(
                    Q(**{
                      "signal1__lead_variant__chrom": chrom,
                      "signal1__lead_variant__pos__gte": start_pos,
                      "signal1__lead_variant__pos__lte": end_pos}) |
                    Q(**{
                      "signal2__lead_variant__chrom": chrom,
                      "signal2__lead_variant__pos__gte": start_pos,
                      "signal2__lead_variant__pos__lte": end_pos})
                )

        return queryset

    region = CharFilter(
        method='filter_region',
        label="Only retrieve results (for signal1 or signal2) within a specified region given as chr:start-end"
    )

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

    signal1_trait = CharFilter(method='filter_signal1_trait', lookup_expr='exact',
                               label="Signal 1 trait UUID")

    def filter_signal1_trait(self, queryset, name, value):
        return queryset.filter(
            Q(no_signal_swap=True, signal1__analysis__trait__uuid=value) |
            Q(no_signal_swap=False, signal2__analysis__trait__uuid=value)
        )

    signal2_trait = CharFilter(method='filter_signal2_trait', lookup_expr='exact',
                               label="Signal 2 trait UUID")

    def filter_signal2_trait(self, queryset, name, value):
        return queryset.filter(
            Q(no_signal_swap=True, signal2__analysis__trait__uuid=value) |
            Q(no_signal_swap=False, signal1__analysis__trait__uuid=value)
        )

    signal1_min_logp = NumberFilter(field_name='signal1__neg_log_p', lookup_expr='gte',
                                    label="Minimum -log10 p-value for signal 1")
    signal2_min_logp = NumberFilter(field_name='signal2__neg_log_p', lookup_expr='gte',
                                    label="Minimum -log10 p-value for signal 2")

    min_h4 = NumberFilter(field_name='coloc_h4', lookup_expr='gte', label="Minimum PP(H4)")
    min_r2 = NumberFilter(field_name='r2', lookup_expr='gte', label="Minimum r2 between the two signals' lead variants")

    order_by_field = 'ordering'
    ordering = NullsLastOrderingFilter(
        # fields(('model field name', 'parameter name used by API request / user'),)
        fields=(
            ('coloc_h3', 'h3'),
            ('coloc_h4', 'h4'),
            ('r2', 'r2'),
            ('n_coloc_between_traits', 'n_coloc_between_traits'),
            *(f"logp_max_over_{e[0].lower()}" for e in ANALYSIS_TYPES),
            ('primary_signal_logp', 'signal1_logp'),
            ('secondary_signal_logp', 'signal2_logp'),
            ('primary_signal_chrom', 'signal1_chrom'),
            ('primary_signal_pos', 'signal1_pos'),
            ('primary_signal_trait', 'signal1_trait'),
            ('secondary_signal_trait', 'signal2_trait'),
            ('secondary_signal_chrom', 'signal2_chrom'),
            ('secondary_signal_pos', 'signal2_pos'),
            ('primary_signal_gene_ens_id', 'signal1_gene_ens_id'),
            ('primary_signal_gene_symbol', 'signal1_gene_symbol'),
            ('primary_signal_tissue', 'signal1_tissue'),
            ('primary_signal_cell_type', 'signal1_cell_type'),
            ('primary_signal_exon_ens_id', 'signal1_exon_ens_id'),
            ('secondary_signal_gene_ens_id', 'signal2_gene_ens_id'),
            ('secondary_signal_gene_symbol', 'signal2_gene_symbol'),
            ('secondary_signal_tissue', 'signal2_tissue'),
            ('secondary_signal_cell_type', 'signal2_cell_type'),
            ('secondary_signal_exon_ens_id', 'signal2_exon_ens_id'),
            ('primary_signal_study', 'signal1_study'),
            ('secondary_signal_study', 'signal2_study')
        )
    )

    class Meta:
        abstract = True
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
            'analysis_types',
            'min_h4',
            'min_r2',
        )


class ColocResultFilter(BaseColocResultFilter):
    """
    Filter for ColocResult model (real colocalization results only).
    """
    class Meta(BaseColocResultFilter.Meta):
        model = models.ColocResult


class ColocResultWithOrphansFilter(BaseColocResultFilter):
    """
    Filter for ColocResultWithOrphans model (includes orphan signals).
    """
    class Meta(BaseColocResultFilter.Meta):
        model = models.ColocResultWithOrphans


class FinemappedSignalResultFilter(FilterSet):
    """
    Default filtering behavior for fine-mapped signal results.
    """

    def create_query(self, field, value):
        if "," in value:
            value = value.split(",")
        else:
            value = [value]

        query = Q(**{f'{field}__in': value})
        return query

    # Create an `all_genes` filter that searches all available gene fields
    genes = CharFilter(
        method='gene_or',
        label="Provide a list of comma-separated genes to filter by. Can be either Ensembl IDs or gene symbols.")

    def gene_or(self, queryset, name, value):
        query = self.create_query('analysis__trait__gene__symbol', value)
        query |= self.create_query('analysis__trait__gene__ens_id', value)
        return queryset.filter(query)

    variants = CharFilter(
        method='variant_or',
        label="Provide a list of comma-separated variant IDs to filter by.")

    def variant_or(self, queryset, name, value):
        query = self.create_query('lead_variant__vid', value)
        return queryset.filter(query)

    cs_variants = CharFilter(
        method='cs_variant_or',
        label="Provide a list of comma-separated credible set variant IDs to filter by.")

    def cs_variant_or(self, queryset, name, value):
        if "," in value:
            variants = value.split(",")
            # For multiple variants, create OR conditions
            query = Q()
            for variant in variants:
                query |= Q(**{'cs_variants__contains': variant})
        else:
            # For single variant
            query = Q(**{'cs_variants__contains': value})
        return queryset.filter(query)

    traits = CharFilter(
        method='trait_or',
        label="Provide a list of comma-separated traits to filter by.")

    def trait_or(self, queryset, name, value):
        """
        Filter on traits.
        """
        query = self.create_query('analysis__trait__uuid', value)
        return queryset.filter(query)

    phenotypes = CharFilter(
        method='phenotype_or',
        label="Provide a list of comma-separated phenotypes to filter by.")

    def phenotype_or(self, queryset, name, value):
        """
        Filter on phenotypes.
        """
        query = self.create_query('analysis__trait__phenotype__name', value)
        return queryset.filter(query)

    tissues = CharFilter(
        method='tissue_or',
        label="Provide a list of comma-separated tissues to filter by.")

    def tissue_or(self, queryset, name, value):
        query = self.create_query('analysis__tissue', value)
        return queryset.filter(query)

    cell_types = CharFilter(
        method='cell_type_or',
        label="Provide a list of comma-separated cell types to filter by.")

    def cell_type_or(self, queryset, name, value):
        query = self.create_query('analysis__cell_type', value)
        return queryset.filter(query)

    analyses = CharFilter(
        method='analysis_uuid_or',
        label="Provide a list of comma-separated marginal analysis UUIDs to filter by.")

    def analysis_uuid_or(self, queryset, name, value):
        query = self.create_query('analysis__uuid', value)
        return queryset.filter(query)

    signals = CharFilter(
        method='signal_or',
        label="Provide a list of comma-separated fine-mapped signal UUIDs to filter by.")

    def signal_or(self, queryset, name, value):
        query = self.create_query('uuid', value)
        return queryset.filter(query)

    studies = CharFilter(
        method='study_or',
        label="Provide a list of comma-separated study UUIDs to filter by.")

    def study_or(self, queryset, name, value):
        query = self.create_query('analysis__study__uuid', value)
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

            pos_field = "lead_variant__pos"
            chrom_field = "lead_variant__chrom"

            return queryset.filter(
                Q(**{f'{chrom_field}': chrom})
                & Q(**{f'{pos_field}__gte': start_pos})
                & Q(**{f'{pos_field}__lte': end_pos})
            )

        return queryset

    region = CharFilter(
        method='filter_region',
        label="Only retrieve signal results within a specified region given as chr:start-end")

    min_logp = NumberFilter(field_name='neg_log_p', lookup_expr='gte', label="Minimum -log10 p-value")

    order_by_field = 'ordering'
    ordering = OrderingFilter(
        fields=(
            ('neg_log_p', 'logp'),
            ('lead_variant__chrom', 'chrom'),
            ('lead_variant__pos', 'pos'),
            ('analysis__trait__uuid', 'trait'),
            ('analysis__trait__gene__ens_id', 'gene_ens_id'),
            ('analysis__trait__exon__ens_id', 'exon_ens_id'),
            ('analysis__trait__gene__symbol', 'gene_symbol'),
            ('analysis__tissue', 'tissue'),
            ('analysis__cell_type', 'cell_type'),
            ('analysis__study__uuid', 'study'),
        )
    )

    class Meta:
        model = models.FineMappedSignal
        fields = (
            'uuid',
            'genes',
            'variants',
            'cs_variants',
            'traits',
            'phenotypes',
            'tissues',
            'cell_types',
            'analyses',
            'signals',
            'studies',
            'region',
            'min_logp',
        )
