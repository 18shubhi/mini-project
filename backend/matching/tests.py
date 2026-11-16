from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from items.models import Item


User = get_user_model()


class ItemMatchesApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="match-owner@example.edu",
            password="CampusFind-Test-2026!",
            name="Report Owner",
            role=User.Role.STUDENT,
        )
        self.other_user = User.objects.create_user(
            email="match-other@example.edu",
            password="CampusFind-Test-2026!",
            name="Other User",
            role=User.Role.FACULTY,
        )
        self.staff = User.objects.create_user(
            email="match-staff@example.edu",
            password="CampusFind-Test-2026!",
            name="Campus Staff",
            role=User.Role.SUPPORTING_STAFF,
            is_staff=True,
        )
        self.lost_item = self.create_item(
            "LOST", "Blue water bottle", "Steel bottle with a mountain sticker."
        )
        self.found_match = self.create_item(
            "FOUND", "Blue bottle found", "Steel water bottle with mountain sticker."
        )
        self.found_unrelated = self.create_item(
            "FOUND", "Red umbrella", "Foldable umbrella left in the gym."
        )
        self.url = reverse("matching:item-matches", args=[self.lost_item.pk])
        self.client.force_authenticate(self.owner)

    def create_item(self, item_type, title, description, reporter=None, **fields):
        return Item.objects.create(
            title=title,
            description=description,
            category=fields.pop("category", Item.Category.WATER_BOTTLES),
            type=item_type,
            date=fields.pop("date", date.today() - timedelta(days=1)),
            location=fields.pop("location", "North Library"),
            status=fields.pop("status", Item.Status.OPEN),
            reporter=reporter or self.owner,
            **fields,
        )

    def test_owner_gets_ranked_opposite_type_open_suggestions(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source_type"], Item.Type.LOST)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["matches"][0]["item"]["id"], self.found_match.id)
        self.assertIn("similarity_score", response.data["matches"][0])
        self.assertIn("matching_details", response.data["matches"][0])

    def test_found_source_can_request_lost_suggestions(self):
        found_source = self.create_item(
            "FOUND", "Blue water bottle", "Steel bottle with mountain sticker."
        )
        response = self.client.get(reverse("matching:item-matches", args=[found_source.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["source_type"], Item.Type.FOUND)
        self.assertTrue(
            all(match["item"]["type"] == Item.Type.LOST for match in response.data["matches"])
        )

    def test_endpoint_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_users_cannot_access_source_report_matches_but_staff_can(self):
        self.client.force_authenticate(self.other_user)
        denied_response = self.client.get(self.url)
        self.client.force_authenticate(self.staff)
        staff_response = self.client.get(self.url)

        self.assertEqual(denied_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(staff_response.status_code, status.HTTP_200_OK)

    def test_invalid_item_id_and_limit_are_rejected(self):
        missing_item = self.client.get(reverse("matching:item-matches", args=[999999]))
        invalid_limit = self.client.get(self.url, {"limit": "many"})
        oversized_limit = self.client.get(self.url, {"limit": "51"})

        self.assertEqual(missing_item.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(invalid_limit.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(oversized_limit.status_code, status.HTTP_400_BAD_REQUEST)

    def test_closed_source_is_rejected_and_closed_candidates_are_omitted(self):
        self.found_unrelated.status = Item.Status.RESOLVED
        self.found_unrelated.save(update_fields=("status",))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [match["item"]["id"] for match in response.data["matches"]],
            [self.found_match.id],
        )

        self.lost_item.status = Item.Status.RESOLVED
        self.lost_item.save(update_fields=("status",))
        closed_response = self.client.get(self.url)
        self.assertEqual(closed_response.status_code, status.HTTP_400_BAD_REQUEST)