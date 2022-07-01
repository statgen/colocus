from django.urls import path

from colocus.api import views
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

    path('studies/', views.AnalysisGroupListView.as_view(), name='studies-all'),
    path('studies/<uuid>/', views.AnalysisGroupDetailView.as_view(), name='studies-detail'),

    path('signals/', views.MarginalSignalListView.as_view(), name='signals-all'),
    path('signals/<uuid>/', views.MarginalSignalDetailView.as_view(), name='signals-detail'),
    path('signals/<uuid>/region/', views.MarginalSignalSummRegionView.as_view(), name='signals-summstats'),

    path('coloc/', views.ColocResultListView.as_view(), name='coloc-all'),
    path('coloc/<uuid>/', views.ColocResultDetailView.as_view(), name='coloc-detail'),

    path('ld/', views.LDPairsListView.as_view(), name='ld-all'),
    path('ld/<uuid>/', views.LDPairsDetailView.as_view(), name='ld-detail'),
    path('ld/<uuid>/region/', views.LDPairsRegionView.as_view(), name='ld-region'),

    # path("v1/", view=user_redirect_view, name="redirect"),
    # path("~update/", view=user_update_view, name="update"),
    # path("<str:username>/", view=user_detail_view, name="detail"),
]
