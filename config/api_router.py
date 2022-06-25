# TODO: In the future we may use DRF native functionality, for now we'll manually control the routes list.

# from django.conf import settings
# from rest_framework.routers import DefaultRouter, SimpleRouter

from colocus.api import urls as api_urls

# from colocus.users.api.views import UserViewSet
#
# if settings.DEBUG:
#     router = DefaultRouter()
# else:
#     router = SimpleRouter()
#
# router.register("users", UserViewSet)


app_name = "api"
urlpatterns = api_urls.urlpatterns  #router.urls
