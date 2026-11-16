from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from items.models import Item
from items.serializers import ItemSerializer

from .services import item_document, rank_matches


class ItemMatchesView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, item_id):
        source = get_object_or_404(Item.objects.select_related("reporter"), pk=item_id)
        user = request.user
        if source.reporter_id != user.id and not user.is_staff and not user.is_superuser:
            raise PermissionDenied("Only the report owner or authorized staff can request matches.")
        if source.status != Item.Status.OPEN:
            raise ValidationError({"item_id": "Only OPEN reports can be matched."})

        try:
            limit = int(request.query_params.get("limit", "10"))
        except ValueError as exc:
            raise ValidationError({"limit": "Limit must be an integer from 1 to 50."}) from exc
        if not 1 <= limit <= 50:
            raise ValidationError({"limit": "Limit must be an integer from 1 to 50."})

        opposite_type = Item.Type.FOUND if source.type == Item.Type.LOST else Item.Type.LOST
        candidates = list(
            Item.objects.select_related("reporter")
            .filter(type=opposite_type, status=Item.Status.OPEN)
            .exclude(pk=source.pk)
        )
        ranked = rank_matches(
            item_document(source),
            [item_document(candidate) for candidate in candidates],
            limit=limit,
        )
        items_by_id = {candidate.pk: candidate for candidate in candidates}
        matches = [
            {
                "item": ItemSerializer(items_by_id[result["candidate"]["id"]]).data,
                "similarity_score": result["similarity_score"],
                "matching_details": result["matching_details"],
            }
            for result in ranked
        ]
        return Response(
            {
                "source_item_id": source.pk,
                "source_type": source.type,
                "count": len(matches),
                "matches": matches,
            },
            status=status.HTTP_200_OK,
        )