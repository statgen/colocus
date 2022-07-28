"""
Views that power internal functionality: non-public API endpoints with additional information required for some pages
"""

from django.http import JsonResponse

from colocus.core import constants, models


def search_page_metadata(request, analysis__uuid):
    """Return metadata required to power the "available categories" menus in the "search" page UI"""
    # TODO: This strongly hardcodes the assumption of two trait types in a single rigid arrangement, GWAS vs eQTL.
    #  We'll need to refactor once we know enough about the other datatypes to decide how they appear in the UI
    trait1_unique = [
        (m.uuid, m.label)
        for m in
        models.MarginalTrait.objects.filter(analysis__uuid=analysis__uuid, trait_type=constants.GWAS)
    ]
    trait2_unique = [
        (m.uuid, m.label)
        for m in
        models.MarginalTrait.objects.filter(analysis__uuid=analysis__uuid, trait_type=constants.EQTL)
    ]
    count_signal_pairs = models.ColocResult.objects.filter(analysis__uuid=analysis__uuid).count()

    return JsonResponse({
        'trait1_unique': trait1_unique,
        'trait2_unique': trait2_unique,
        'count_pairs': count_signal_pairs,
    })
