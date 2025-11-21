# TODO: In the future we may use DRF native functionality, for now we'll manually control the routes list.

# from django.conf import settings
# from rest_framework.routers import DefaultRouter, SimpleRouter

from django.urls import include, path

from colocus.api import urls as api_urls

# from colocus.users.api.views import UserViewSet
#
# if settings.DEBUG:
#     router = DefaultRouter()
# else:
#     router = SimpleRouter()
#
# router.register("users", UserViewSet)


urlpatterns = [
    path("v1/", include((api_urls.urls_v1, "api"), namespace="v1")),
    # path('v2/', include((api_urls.urls_v2, 'api'), namespace='v2')),
]
