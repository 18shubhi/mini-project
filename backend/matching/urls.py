from django.urls import path

from .views import ItemMatchesView


app_name = "matching"

urlpatterns = [
    path("items/<int:item_id>/suggestions/", ItemMatchesView.as_view(), name="item-matches"),
]