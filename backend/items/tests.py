import io
import tempfile
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import Item


User = get_user_model()


class ItemApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.edu",
            password="CampusFind-Test-2026!",
            name="Item Owner",
            role=User.Role.STUDENT,
        )
        self.other_user = User.objects.create_user(
            email="other@example.edu",
            password="CampusFind-Test-2026!",
            name="Other User",
            role=User.Role.FACULTY,
        )
        self.staff = User.objects.create_user(
            email="staff@example.edu",
            password="CampusFind-Test-2026!",
            name="Campus Staff",
            role=User.Role.SUPPORTING_STAFF,
            is_staff=True,
        )
        self.list_url = reverse("items:item-list")
        self.client.force_authenticate(self.owner)

    def payload(self, **overrides):
        payload = {
            "title": "Blue water bottle",
            "description": "A blue bottle near the library.",
            "category": Item.Category.WATER_BOTTLES,
            "type": Item.Type.LOST,
            "date": (date.today() - timedelta(days=1)).isoformat(),
            "location": "Main Library",
        }
        payload.update(overrides)
        return payload

    def image_upload(self, name="bottle.png"):
        buffer = io.BytesIO()
        Image.new("RGB", (1, 1), color="blue").save(buffer, format="PNG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

    def create_item(self, **overrides):
        return Item.objects.create(reporter=self.owner, **self.payload(**overrides))

    def test_create_lost_and_found_reports_associates_authenticated_user(self):
        lost = self.client.post(self.list_url, self.payload(), format="json")
        found = self.client.post(
            self.list_url,
            self.payload(type=Item.Type.FOUND, title="Found keys"),
            format="json",
        )

        self.assertEqual(lost.status_code, status.HTTP_201_CREATED)
        self.assertEqual(found.status_code, status.HTTP_201_CREATED)
        self.assertEqual(lost.data["reporter"]["id"], self.owner.id)
        self.assertEqual(lost.data["type"], Item.Type.LOST)
        self.assertEqual(found.data["type"], Item.Type.FOUND)

    def test_create_requires_authentication_and_jwt_token_works(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        token = AccessToken.for_user(self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_and_retrieve_reports(self):
        item = self.create_item()

        list_response = self.client.get(self.list_url)
        detail_response = self.client.get(reverse("items:item-detail", args=[item.id]))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["title"], item.title)

    def test_owner_can_update_and_delete_report(self):
        item = self.create_item()

        update_response = self.client.patch(
            reverse("items:item-detail", args=[item.id]),
            {"title": "Updated bottle", "status": Item.Status.RESOLVED},
            format="json",
        )
        delete_response = self.client.delete(
            reverse("items:item-detail", args=[item.id])
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["status"], Item.Status.OPEN)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Item.objects.filter(pk=item.pk).exists())

    def test_only_owner_or_django_staff_can_modify_or_delete(self):
        item = self.create_item()
        detail_url = reverse("items:item-detail", args=[item.id])
        self.client.force_authenticate(self.other_user)

        update_response = self.client.patch(
            detail_url, {"title": "Unauthorized change"}, format="json"
        )
        delete_response = self.client.delete(detail_url)

        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.staff)
        staff_response = self.client.patch(
            detail_url, {"title": "Staff update"}, format="json"
        )
        self.assertEqual(staff_response.status_code, status.HTTP_200_OK)

    def test_invalid_item_data_is_rejected(self):
        response = self.client.post(
            self.list_url,
            self.payload(type="MISSING", date="not-a-date"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filters_by_type_category_name_location_and_date(self):
        matching = self.create_item()
        self.create_item(
            type=Item.Type.FOUND,
            title="Black wallet",
            category=Item.Category.BAGS_WALLETS,
            location="Student Center",
        )
        params = {
            "type": "LOST",
            "category": Item.Category.WATER_BOTTLES,
            "name": "blue",
            "location": "library",
            "date": matching.date,
        }

        response = self.client.get(self.list_url, params)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([entry["id"] for entry in response.data], [matching.id])

    def test_invalid_date_filter_returns_validation_error(self):
        response = self.client.get(self.list_url, {"date": "yesterday"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_image_upload_validates_type_and_size(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                valid_response = self.client.post(
                    self.list_url,
                    {**self.payload(), "image": self.image_upload()},
                    format="multipart",
                )
                self.assertEqual(valid_response.status_code, status.HTTP_201_CREATED)
                self.assertIn("/media/items/", valid_response.data["image"])

            with override_settings(MEDIA_ROOT=media_root, ITEM_IMAGE_MAX_SIZE=10):
                oversized_response = self.client.post(
                    self.list_url,
                    {**self.payload(), "image": self.image_upload("large.png")},
                    format="multipart",
                )
            self.assertEqual(oversized_response.status_code, status.HTTP_400_BAD_REQUEST)

        invalid_image_response = self.client.post(
            self.list_url,
            {
                **self.payload(),
                "image": SimpleUploadedFile(
                    "invalid.png", b"not an image", content_type="image/png"
                ),
            },
            format="multipart",
        )
        self.assertEqual(invalid_image_response.status_code, status.HTTP_400_BAD_REQUEST)