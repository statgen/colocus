from django.urls import path

from colocus.api import internal_views, views

# .views import (
#     user_detail_view,
#     user_redirect_view,
#     user_update_view,
# )

urlpatterns = [
    # New API endpoints that can optionally take an analysis_uuid as GET parameter
    # These endpoints do not require an analysis_uuid as they are not study-specific

    # Colocalization results
    path('coloc/', views.ColocResultListView.as_view(), name='coloc-all'),
    path('coloc/<uuid>/', views.ColocResultDetailView.as_view(), name='coloc-detail'),
    path(
        'signals/<uuid>/region/',
        views.MarginalSignalSummRegionView.as_view(),
        name='signals-summstats'
    ),
    path('traits/', views.MarginalTraitListView.as_view(), name='traits-all'),
    path('traits/<uuid>/', views.MarginalTraitDetailView.as_view(), name='traits-detail'),
    path(
        'internal/search_metadata/',
        internal_views.search_page_metadata,
        name='search-metadata'
    ),
    path(
        'internal/traits/<uuid>/manhattan/',
        internal_views.trait_manhattan,
        name='trait-manhattan'
    ),
    path('ld/', views.LDPairsListView.as_view(), name='ld-all'),
    path('ld/<uuid>/', views.LDPairsDetailView.as_view(), name='ld-detail'),
    path('ld/<uuid>/region/', views.LDPairsRegionView.as_view(), name='ld-region'),

    ### Study specific endpoints

    # # List of studies / datasets
    path('studies/', views.AnalysisGroupListView.as_view(), name='studies-all'),

    # path('studies/<uuid>/', views.AnalysisGroupDetailView.as_view(), name='studies-detail'),
    #
    # # Marginal trait data (used to render "trait detail view" pages). Some trait info is embedded into the coloc
    # # result view without a separate API call.
    # path('studies/<analysis_uuid>/traits/', views.MarginalTraitListView.as_view(), name='traits-all'),
    # path('studies/<analysis_uuid>/traits/<uuid>/', views.MarginalTraitDetailView.as_view(), name='traits-detail'),
    #
    # # List of unique signals (individual, LD-distinct peaks, usually within a particular locus. Provides both marg
    # # and cond analysis results)
    # path('studies/<analysis_uuid>/signals/', views.MarginalSignalListView.as_view(), name='signals-all'),
    # path('studies/<analysis_uuid>/signals/<uuid>/', views.MarginalSignalDetailView.as_view(), name='signals-detail'),
    # path(
    #     'studies/<analysis_uuid>/signals/<uuid>/region/',
    #     views.MarginalSignalSummRegionView.as_view(),
    #     name='signals-summstats'
    # ),
    #
    # # Colocalization analysis: estimated probability of two results supporting the same peak
    # # for a given trait + signal pair
    # path('studies/<analysis_uuid>/coloc/', views.ColocResultListView.as_view(), name='coloc-all'),
    # path('studies/<analysis_uuid>/coloc/<uuid>/', views.ColocResultDetailView.as_view(), name='coloc-detail'),
    #
    # # LD data and metadata for a given dataset
    # path('studies/<analysis_uuid>/ld/', views.LDPairsListView.as_view(), name='ld-all'),
    # path('studies/<analysis_uuid>/ld/<uuid>/', views.LDPairsDetailView.as_view(), name='ld-detail'),
    # path('studies/<analysis_uuid>/ld/<uuid>/region/', views.LDPairsRegionView.as_view(), name='ld-region'),
    #
    # # "Private" endpoints only used by internal views. These may change and carry no external contract of stability.
    # path(
    #     'internal/studies/<analysis__uuid>/search_metadata/',
    #     internal_views.search_page_metadata,
    #     name='search-metadata'
    # ),
    # path(
    #     'internal/studies/<analysis_uuid>/traits/<uuid>/manhattan/',
    #     internal_views.trait_manhattan,
    #     name='trait-manhattan'
    # ),
    # path('internal/studies/<analysis_uuid>/traits/<uuid>/qq/', internal_views.trait_qq, name='trait-qq'),
    #
    # path('internal/genes', internal_views.MarginalSignalGeneView, name='genes'),

    # path("v1/", view=user_redirect_view, name="redirect"),
    # path("~update/", view=user_update_view, name="update"),
    # path("<str:username>/", view=user_detail_view, name="detail"),
]
