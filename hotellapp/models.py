from __future__ import annotations

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone


class Room(models.Model):
    class Type(models.TextChoices):
        SINGLE = "single", "Single"
        DOUBLE = "double", "Double"
        TWIN = "twin", "Twin"
        SUITE = "suite", "Suite"
        APARTMENT = "apartment", "Serviced Apartment"
        JUNIOR_SUITE = "junior_suite", "Junior Suite"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        OCCUPIED = "occupied", "Occupied"
        CLEANING = "cleaning", "Cleaning"

    number = models.CharField(max_length=10, unique=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.DOUBLE)
    price_per_night = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.AVAILABLE)

    def __str__(self) -> str:  # pragma: no cover
        return f"Room {self.number} - {self.get_type_display()} ({self.get_status_display()})"


class Client(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.first_name} {self.last_name}".strip()


class Reservation(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Booked"
        CHECKED_IN = "checked_in", "Checked-in"
        CHECKED_OUT = "checked_out", "Checked-out"
        CANCELED = "canceled", "Canceled"

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="reservations")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="reservations")
    check_in = models.DateField()
    check_out = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BOOKED)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(name="check_in_before_check_out", check=Q(check_in__lt=F("check_out"))),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"Reservation #{self.pk or 'new'} - Room {self.room.number} for {self.client} [{self.check_in} → {self.check_out}]"

    @property
    def nights(self) -> int:
        return max(0, (self.check_out - self.check_in).days)

    def clean(self) -> None:
        # Basic date validation
        if self.check_in and self.check_out and self.check_in >= self.check_out:
            raise ValidationError({"check_out": "Check-out must be after check-in."})

        # Availability validation: no overlaps with active reservations for same room
        if self.room_id and self.check_in and self.check_out:
            overlapping = (
                Reservation.objects.filter(room_id=self.room_id)
                .exclude(pk=self.pk)
                .filter(
                    status__in=[Reservation.Status.BOOKED, Reservation.Status.CHECKED_IN],
                    check_in__lt=self.check_out,
                    check_out__gt=self.check_in,
                )
                .exists()
            )
            if overlapping:
                raise ValidationError("Selected room is not available for the given dates.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Invoice(models.Model):
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name="invoice")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="invoices")
    issue_date = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="EUR")
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-issue_date"]

    def __str__(self) -> str:  # pragma: no cover
        return f"Invoice #{self.pk or 'new'} for {self.client} ({self.total} {self.currency})"

    def compute_total(self) -> Decimal:
        nights = self.reservation.nights
        price = self.reservation.room.price_per_night
        return (Decimal(nights) * price).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        # Auto-calculate total if not set or when saving
        self.total = self.compute_total()
        super().save(*args, **kwargs)

    def as_dict(self) -> dict:
        return {
            "invoice_id": self.pk,
            "issue_date": self.issue_date,
            "client": f"{self.client.first_name} {self.client.last_name}",
            "room": f"{self.reservation.room.number} - {self.reservation.room.get_type_display()}",
            "check_in": self.reservation.check_in.isoformat(),
            "check_out": self.reservation.check_out.isoformat(),
            "nights": self.reservation.nights,
            "price_per_night": str(self.reservation.room.price_per_night),
            "total": str(self.total),
            "currency": self.currency,
        }

    def render_pdf(self):
        """
        Placeholder for PDF generation.

        Suggested implementation paths:
        - WeasyPrint:
            from django.template.loader import render_to_string
            from weasyprint import HTML
            html = render_to_string("hotellapp/invoice_pdf.html", {"invoice": self})
            HTML(string=html).write_pdf(target=some_file_path_or_response)
        - ReportLab:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(file_path, pagesize=A4)
            # draw strings...
            c.save()

        Keep this method returning an HttpResponse for direct download when you wire it up.
        """
        raise NotImplementedError("PDF generation not implemented. See docstring for guidance.")
