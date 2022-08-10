"""
Custom DRF pagination class that allows client to control the page size
https://www.django-rest-framework.org/api-guide/pagination/
"""
from rest_framework.pagination import PageNumberPagination


class ResizablePageNumberPagination(PageNumberPagination):
    """Allow certain overview pages to show more data than otherwise would be allowed"""
    page_size_query_param = 'page_size'
    max_page_size = 250
