import logging

from django.utils.dateparse import parse_date
from rest_framework import filters, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from .models import Item
from .permissions import IsOwnerOrStaff
from .serializers import ItemSerializer


logger = logging.getLogger(__name__)


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.select_related("reporter").all()
    serializer_class = ItemSerializer
    permission_classes = (IsAuthenticated, IsOwnerOrStaff)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("title", "description", "category", "location")
    ordering_fields = ("created_at", "date", "title")

    def get_queryset(self):
        queryset = super().get_queryset()
        query_params = self.request.query_params

        item_type = query_params.get("type")
        if item_type:
            queryset = queryset.filter(type__iexact=item_type)

        category = query_params.get("category")
        if category:
            queryset = queryset.filter(category__iexact=category)

        name = query_params.get("name")
        if name:
            queryset = queryset.filter(title__icontains=name)

        location = query_params.get("location")
        if location:
            queryset = queryset.filter(location__icontains=location)

        item_date = query_params.get("date")
        if item_date:
            parsed_date = parse_date(item_date)
            if parsed_date is None:
                raise ValidationError({"date": "Use the YYYY-MM-DD format."})
            queryset = queryset.filter(date=parsed_date)

        return queryset

    def perform_create(self, serializer):
        item = serializer.save(reporter=self.request.user)
        from notifications.services import notify_potential_matches

        try:
            notify_potential_matches(item)
        except Exception:
            logger.exception("Could not create potential-match notifications for item %s", item.pk)