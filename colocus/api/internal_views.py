"""
Views that power internal functionality: non-public API endpoints with additional information required for some pages
"""
import os

from django import http

from colocus.core import constants, models

# import re
# import json

# from django.conf import settings


# from django.db.models import CharField, F, Q, Value


def search_page_metadata(request, *args, **kwargs):
    # Apply analysis_uuid filter if provided, else use all objects
    qs_analysis = models.MarginalAnalysis.objects.select_related(
        "trait",
        "trait__phenotype",
        "study")

    """Return metadata required to power the "available categories" menus in the "search" page UI"""
    count_signal_pairs = models.ColocResult.objects.count()

    analysis_types = set()
    tissues = set()
    phenotypes = set()
    studies = set()

    analysis_fields = ["analysis_type", "tissue", "trait__phenotype__name", "study__uuid"]
    for obj in qs_analysis.values(*analysis_fields):
        analysis_types.add(obj.get("analysis_type"))
        tissues.add(obj.get("tissue"))
        phenotypes.add(obj.get("trait__phenotype__name"))
        studies.add(obj.get("study__uuid"))

    for s in [analysis_types, tissues, phenotypes, studies]:
        s.discard(None)

    analysis_types = list(analysis_types)
    tissues = list(tissues)
    phenotypes = list(phenotypes)
    studies = list(studies)

    # Extract the genes from both signal1 and signal2 traits
    # This uses .values() to avoid pulling in a lot of unnecessary data and avoids issues with prefetching and
    # customizing the serializer for this one case
    fields = [
        'signal1__analysis__trait__gene__ens_id',
        'signal1__analysis__trait__gene__symbol',
        'signal2__analysis__trait__gene__ens_id',
        'signal2__analysis__trait__gene__symbol',
    ]
    coloc_results = models.ColocResult.objects.values(*fields)
    genes = set()
    for coloc in coloc_results:
        for i in range(1, 3):
            ens = coloc.get(f"signal{i}__analysis__trait__gene__ens_id")
            symb = coloc.get(f"signal{i}__analysis__trait__gene__symbol")
            if ens:
                genes.add(ens)
            if symb:
                genes.add(symb)

    result = {
        'count_pairs': count_signal_pairs,
        'tissues': tissues,
        'analysis_types': analysis_types,
        'phenotypes': phenotypes,
        'studies': studies,
        'genes': list(genes)
    }

    # For debugging: Return data as HTML
    # This allows Django debug toolbar to show up
    # if settings.DEBUG:
    #     html = "<html><body><pre>{}</pre></body></html>".format(json.dumps(result, indent=4))
    #     return http.HttpResponse(html)

    return http.JsonResponse(result)


# TODO: DRY manhattan / qq views
def analysis_manhattan(request, *args, **kwargs):
    """
    Return the data used to render a manhattan plot. This only makes sense for a GWAS; other traits, like cis-eQTLs,
      may be defined only around a specific locus, and can't meaningfully be visualized genome wide
    """

    filter_args = {"uuid": kwargs.get("uuid")}

    try:
        model = models.MarginalAnalysis.objects.get(**filter_args)
    except models.MarginalAnalysis.DoesNotExist:
        return http.HttpResponseNotFound("No record was found for the specified study + trait")

    filename = model.manhattan_bins.path
    if not model.analysis_type == constants.GWAS or not model.manhattan_bins or not os.path.exists(filename):
        return http.HttpResponseBadRequest("No manhattan data is available for the specified trait")

    return http.FileResponse(open(filename, 'rb'), content_type='application/json')


def analysis_qq(request, uuid):
    """
    Return the data used to render a QQ plot. We're only going to provide this feature for a GWAS for now, because other
      traits (like cis-eQTLs) may be evaluated locally, and inspecting the QQ plot in "only a region of high signal"
      might be misleading.
      TODO Currently this is tied to a local filesystem. May need to refactor if we switch to S3.
    """
    try:
        model = models.MarginalAnalysis.objects.get(uuid=uuid)
    except models.MarginalAnalysis.DoesNotExist:
        return http.HttpResponseNotFound("No record was found for the specified study + trait")

    filename = model.qq_bins.path
    if not model.analysis_type == constants.GWAS or not model.qq_bins or not os.path.exists(filename):
        return http.HttpResponseBadRequest("No QQ data is available for the specified trait")

    return http.FileResponse(open(filename, 'rb'), content_type='application/json')
