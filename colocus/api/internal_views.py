"""
Views that power internal functionality: non-public API endpoints with additional information required for some pages
"""
import os

from django import http

from colocus.core import constants, models


def search_page_metadata(request, analysis__uuid):
    """Return metadata required to power the "available categories" menus in the "search" page UI"""
    count_signal_pairs = models.ColocResult.objects.filter(analysis__uuid=analysis__uuid).count()

    # Trait types seen across all signals
    trait_types = list(set(
        m.trait_type
        for m in
        models.MarginalTrait.objects.filter(analysis__uuid=analysis__uuid)
    ))

    # Get list of available tissues
    tissues = list(set(
        m.metadata["tissue"]
        for m in
        models.MarginalTrait.objects.filter(analysis__uuid=analysis__uuid, trait_type=constants.EQTL)
    ))

    # Get list of all possible traits
    phenotypes = list(set(
        m.metadata["trait"]
        for m in
        models.MarginalTrait.objects.filter(analysis__uuid=analysis__uuid, trait_type=constants.GWAS)
    ))

    studies = list(set(
        m.study_name
        for m in models.MarginalTrait.objects.filter(analysis__uuid=analysis__uuid)
    ))

    return http.JsonResponse({
        'count_pairs': count_signal_pairs,
        'tissues': tissues,
        'trait_types': trait_types,
        'phenotypes': phenotypes,
        'studies': studies
    })


# TODO: DRY manhattan / qq views
def trait_manhattan(request, analysis_uuid, uuid):
    """
    Return the data used to render a manhattan plot. This only makes sense for a GWAS; other traits, like cis-eQTLs,
      may be defined only around a specific locus, and can't meaningfully be visualized genome wide
      TODO Currently this is tied to a local filesystem. May need to refactor if we switch to S3.
    """
    try:
        model = models.MarginalTrait.objects.get(analysis__uuid=analysis_uuid, uuid=uuid)
    except models.MarginalTrait.DoesNotExist:
        return http.HttpResponseNotFound("No record was found for the specified study + trait")

    filename = model.manhattan_bins.path
    if not model.trait_type == constants.GWAS or not model.manhattan_bins or not os.path.exists(filename):
        return http.HttpResponseBadRequest("No manhattan data is available for the specified trait")

    return http.FileResponse(open(filename, 'rb'), content_type='application/json')


def trait_qq(request, analysis_uuid, uuid):
    """
    Return the data used to render a QQ plot. We're only going to provide this feature for a GWAS for now, because other
      traits (like cis-eQTLs) may be evaluated locally, and inspecting the QQ plot in "only a region of high signal"
      might be misleading.
      TODO Currently this is tied to a local filesystem. May need to refactor if we switch to S3.
    """
    try:
        model = models.MarginalTrait.objects.get(analysis__uuid=analysis_uuid, uuid=uuid)
    except models.MarginalTrait.DoesNotExist:
        return http.HttpResponseNotFound("No record was found for the specified study + trait")

    filename = model.qq_bins.path
    if not model.trait_type == constants.GWAS or not model.qq_bins or not os.path.exists(filename):
        return http.HttpResponseBadRequest("No QQ data is available for the specified trait")

    return http.FileResponse(open(filename, 'rb'), content_type='application/json')
