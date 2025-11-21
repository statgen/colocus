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

# Keeping the two examples below for future reference. They are extremely fast, but do not allow pagination or caching,
# which could be a problem for much larger datasets in the future. The current implementation is slower, but allows
# for pagination and caching, and are only marginally slower.

# def signals_slim(request, *args, **kwargs):
#     """
#     Return a slimmed down version all signals, with only the fields required for making QC figures
#     """
#
#     fields = """
#         uuid
#         analysis__uuid
#         analysis__analysis_type
#         analysis__trait__uuid
#         analysis__dataset__uuid
#         analysis__tissue
#         analysis__study__uuid
#         lead_variant__vid
#     """.split()
#
#     # Change objects into JSON response
#     objects = models.FineMappedSignal.objects.values(*fields)
#     result = []
#     for obj in objects:
#         result.append({
#             "uuid": obj.get("uuid"),
#             "analysis": {
#                 "uuid": obj.get("analysis__uuid"),
#                 "dataset": {
#                     "uuid": obj.get("analysis__dataset__uuid"),
#                 },
#                 "analysis_type": obj.get("analysis__analysis_type"),
#                 "trait": {
#                     "uuid": obj.get("analysis__trait__uuid"),
#                 },
#                 "tissue": obj.get("analysis__tissue"),
#                 "study": {
#                     "uuid": obj.get("analysis__study__uuid"),
#                 }
#             },
#             "lead_variant": {
#                 "vid": obj.get("lead_variant__vid")
#             }
#         })
#
#     return http.JsonResponse({
#         "count": len(result),
#         "results": result
#     })
#
#
# def coloc_slim(request, *args, **kwargs):
#     """
#     Return a slimmed down version of the coloc results, with only the fields required for making QC figures
#     """
#
#     fields = """
#         uuid
#         signal1__analysis__uuid
#         signal1__analysis__analysis_type
#         signal1__analysis__trait__uuid
#         signal1__analysis__dataset__uuid
#         signal1__analysis__tissue
#         signal1__analysis__study__uuid
#         signal1__lead_variant__vid
#         signal2__analysis__uuid
#         signal2__analysis__analysis_type
#         signal2__analysis__trait__uuid
#         signal2__analysis__dataset__uuid
#         signal2__analysis__tissue
#         signal2__analysis__study__uuid
#         signal2__lead_variant__vid
#         coloc_h4
#         r2
#     """.split()
#
#     # Change objects into JSON response
#     objects = models.ColocResult.objects.values(*fields)
#     result = []
#     for obj in objects:
#         result.append({
#             "uuid": obj.get("uuid"),
#             "signal1": {
#                 "analysis": {
#                     "uuid": obj.get("signal1__analysis__uuid"),
#                     "dataset": {
#                         "uuid": obj.get("signal1__analysis__dataset__uuid"),
#                     },
#                     "analysis_type": obj.get("signal1__analysis__analysis_type"),
#                     "trait": {
#                         "uuid": obj.get("signal1__analysis__trait__uuid"),
#                     },
#                     "tissue": obj.get("signal1__analysis__tissue"),
#                     "study": {
#                         "uuid": obj.get("signal1__analysis__study__uuid"),
#                     }
#                 },
#                 "lead_variant": {
#                     "vid": obj.get("signal1__lead_variant__vid")
#                 }
#             },
#             "signal2": {
#                 "analysis": {
#                     "uuid": obj.get("signal2__analysis__uuid"),
#                     "dataset": {
#                         "uuid": obj.get("signal2__analysis__dataset__uuid"),
#                     },
#                     "analysis_type": obj.get("signal2__analysis__analysis_type"),
#                     "trait": {
#                         "uuid": obj.get("signal2__analysis__trait__uuid"),
#                     },
#                     "tissue": obj.get("signal2__analysis__tissue"),
#                     "study": {
#                         "uuid": obj.get("signal2__analysis__study__uuid"),
#                     }
#                 },
#                 "lead_variant": {
#                     "vid": obj.get("signal2__lead_variant__vid")
#                 }
#             },
#             "coloc_h4": float(format(obj.get("coloc_h4"), '.3g')),
#             "r2": float(format(obj.get("r2"), '.3g')),
#         })
#
#     return http.JsonResponse({
#         "count": len(result),
#         "results": result
#     })


def search_page_metadata(request, *args, **kwargs):
    # Apply analysis_uuid filter if provided, else use all objects
    qs_analysis = models.MarginalAnalysis.objects.select_related(
        "trait", "trait__phenotype", "study"
    )

    """Return metadata required to power the "available categories" menus in the "search" page UI"""
    count_signal_pairs = models.ColocResult.objects.count()

    analysis_types = set()
    tissues = set()
    cell_types = set()
    phenotypes = set()
    studies = set()

    analysis_fields = [
        "analysis_type",
        "tissue",
        "cell_type",
        "trait__phenotype__name",
        "study__uuid",
    ]
    for obj in qs_analysis.values(*analysis_fields):
        analysis_types.add(obj.get("analysis_type"))
        tissues.add(obj.get("tissue"))
        cell_types.add(obj.get("cell_type"))
        phenotypes.add(obj.get("trait__phenotype__name"))
        studies.add(obj.get("study__uuid"))

    for s in [analysis_types, tissues, cell_types, phenotypes, studies]:
        s.discard(None)

    analysis_types = list(analysis_types)
    tissues = list(tissues)
    cell_types = list(cell_types)
    phenotypes = list(phenotypes)
    studies = list(studies)

    # Extract the genes from both signal1 and signal2 traits
    # This uses .values() to avoid pulling in a lot of unnecessary data and avoids issues with prefetching and
    # customizing the serializer for this one case
    fields = [
        "signal1__analysis__trait__gene__ens_id",
        "signal1__analysis__trait__gene__symbol",
        "signal2__analysis__trait__gene__ens_id",
        "signal2__analysis__trait__gene__symbol",
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
        "count_pairs": count_signal_pairs,
        "tissues": tissues,
        "cell_types": cell_types,
        "analysis_types": analysis_types,
        "phenotypes": phenotypes,
        "studies": studies,
        "genes": list(genes),
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
        return http.HttpResponseNotFound(
            "No record was found for the specified study + trait"
        )

    filename = model.manhattan_bins
    if (
        not model.analysis_type == constants.GWAS
        or not model.manhattan_bins
        or not os.path.exists(filename)
    ):
        return http.HttpResponseBadRequest(
            "No manhattan data is available for the specified trait"
        )

    return http.FileResponse(open(filename, "rb"), content_type="application/json")


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
        return http.HttpResponseNotFound(
            "No record was found for the specified study + trait"
        )

    filename = model.qq_bins
    if (
        not model.analysis_type == constants.GWAS
        or not model.qq_bins
        or not os.path.exists(filename)
    ):
        return http.HttpResponseBadRequest(
            "No QQ data is available for the specified trait"
        )

    return http.FileResponse(open(filename, "rb"), content_type="application/json")
