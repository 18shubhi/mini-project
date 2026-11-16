from django.conf import settings
from django.db import models


class Item(models.Model):
    class Category(models.TextChoices):
        ELECTRONICS = "Electronics", "Electronics"
        BOOKS_NOTES = "Books & Notes", "Books & Notes"
        BAGS_WALLETS = "Bags & Wallets", "Bags & Wallets"
        CLOTHING = "Clothing", "Clothing"
        KEYS_ID_CARDS = "Keys & ID Cards", "Keys & ID Cards"
        WATER_BOTTLES = "Water Bottles", "Water Bottles"
        ACCESSORIES = "Accessories", "Accessories"
        OTHER = "Other", "Other"

    class Type(models.TextChoices):
        LOST = "LOST", "Lost"
        FOUND = "FOUND", "Found"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESOLVED = "RESOLVED", "Resolved"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=32, choices=Category.choices)
    type = models.CharField(max_length=5, choices=Type.choices)
    date = models.DateField()
    location = models.CharField(max_length=255)
    image = models.ImageField(upload_to="items/%Y/%m/", blank=True, null=True)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="item_reports",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("type", "status", "date"))]

    def __str__(self):
        return f"{self.get_type_display()}: {self.title}"