from django.urls import path

from colocus.api import internal_views, views
# .views import (
#     user_detail_view,
#     user_redirect_view,
#     user_update_view,
# )

app_name = "api"
urlpatterns = [
    # FIXME:
    # /signals = LISTVIEW
    #     /<uid>/ (DETAILVIEW = metadata describing which trait and lead variant this is for)
    #     /<uid>/summ_stats/ = (joined summary stats: marg trait + cond analysis)
    # /coloc/ = LISTVIEW
    #     /<uid> = metadata: what are the two signals + h3/h4 for this item? Used for region plot page
    # /ld/ = LISTVIEW
    #     /<uid>/ ?chr-start-end - retrieve LD for a given view, translate to LZ api fields. Uses panel ID from marg trait page

    # List of studies / datasets
    path('studies/', views.AnalysisGroupListView.as_view(), name='studies-all'),
    path('studies/<uuid>/', views.AnalysisGroupDetailView.as_view(), name='studies-detail'),

    # List of unique signals (individual, LD-distinct peaks, usually within a particular locus. Provides both marg and cond analysis results)
    path('studies/<analysis_uuid>/signals/', views.MarginalSignalListView.as_view(), name='signals-all'),
    path('studies/<analysis_uuid>/signals/<uuid>/', views.MarginalSignalDetailView.as_view(), name='signals-detail'),
    path('studies/<analysis_uuid>/signals/<uuid>/region/', views.MarginalSignalSummRegionView.as_view(), name='signals-summstats'),

    # Colocalization analysis: estimated probability of two results supporting the same peak for a given trait + signal pair
    path('studies/<analysis_uuid>/coloc/', views.ColocResultListView.as_view(), name='coloc-all'),
    path('studies/<analysis_uuid>/coloc/<uuid>/', views.ColocResultDetailView.as_view(), name='coloc-detail'),

    # LD data and metadata for a given dataset
    path('studies/<analysis_uuid>/ld/', views.LDPairsListView.as_view(), name='ld-all'),
    path('studies/<analysis_uuid>/ld/<uuid>/', views.LDPairsDetailView.as_view(), name='ld-detail'),
    path('studies/<analysis_uuid>/ld/<uuid>/region/', views.LDPairsRegionView.as_view(), name='ld-region'),

    # "Private" endpoints only used by internal views. These may change and carry no external contract of stability.
    path('internal/studies/<analysis__uuid>/search_metadata/', internal_views.search_page_metadata, name='search-metadata'),
    path('internal/studies/<analysis_uuid>/traits/<uuid>/manhattan/', internal_views.trait_manhattan, name='trait-manhattan'),
    path('internal/studies/<analysis_uuid>/traits/<uuid>/qq/', internal_views.trait_qq, name='trait-qq'),

    # path("v1/", view=user_redirect_view, name="redirect"),
    # path("~update/", view=user_update_view, name="update"),
    # path("<str:username>/", view=user_detail_view, name="detail"),
]
