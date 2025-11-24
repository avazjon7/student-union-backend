# from django.db import models
# from apps.events.models import Registration, PaymentStatus
#
#
# class PaymentProvider(models.TextChoices):
#     CLICK = "click", "Click"
#     PAYME = "payme", "Payme"
#     UZUM = "uzum", "Uzum"
#     MANUAL = "manual", "Manual"
#     UNKNOWN = "unknown", "Unknown"
#
#
# class Payment(models.Model):
#     registration = models.ForeignKey(
#         Registration,
#         on_delete=models.CASCADE,
#         related_name="payments",
#     )
#     provider = models.CharField(
#         max_length=20,
#         choices=PaymentProvider.choices,
#         default=PaymentProvider.MANUAL,
#     )
#     amount = models.PositiveIntegerField()
#     status = models.CharField(
#         max_length=20,
#         choices=PaymentStatus.choices,
#         default=PaymentStatus.PENDING,
#     )
#     provider_txn_id = models.CharField(max_length=255, blank=True)
#     raw_payload = models.JSONField(null=True, blank=True)
#
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#
#     class Meta:
#         ordering = ["-created_at"]
#
#     def __str__(self) -> str:
#         return f"{self.provider} {self.amount} ({self.status})"
