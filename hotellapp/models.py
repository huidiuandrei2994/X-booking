from __future__ import annotations

from decimal import Decimal
from datetime import date, timedelta
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

    def get_price_for_date(self, d: date) -> Decimal:
        """
        Return the nightly price for this room on a given date, using the most specific active season:
        1) Room-specific RateSeason covering the date
        2) Room-type RateSeason covering the date
        3) Fallback to room.price_per_night

        Honors RateSeason.apply_on: all/weekdays/weekends.
        """
        # Determine which apply_on values are valid for this date
        allowed_apply_on = [RateSeason.ApplyOn.ALL]
        if d.weekday() < 5:
            allowed_apply_on.append(RateSeason.ApplyOn.WEEKDAYS)
        else:
            allowed_apply_on.append(RateSeason.ApplyOn.WEEKENDS)

        # Room-specific season
        season = RateSeason.objects.filter(
            active=True,
            room=self,
            start_date__lte=d,
            end_date__gte=d,
            apply_on__in=allowed_apply_on,
        ).order_by("-start_date").first()
        if season:
            return season.price

        # Room-type season
        season = RateSeason.objects.filter(
            active=True,
            room__isnull=True,
            room_type=self.type,
            start_date__lte=d,
            end_date__gte=d,
            apply_on__in=allowed_apply_on,
        ).order_by("-start_date").first()
        if season:
            return season.price

        return self.price_per_night


class RateSeason(models.Model):
    """
    Seasonal pricing rule. If 'room' is set, it overrides 'room_type' for that room.
    If only 'room_type' is set, it applies to all rooms of that type.
    'apply_on' controls which days are affected (all/weekdays/weekends).
    """
    class ApplyOn(models.TextChoices):
        ALL = "all", "All days"
        WEEKDAYS = "weekdays", "Weekdays (Mon–Fri)"
        WEEKENDS = "weekends", "Weekends (Sat–Sun)"

    name = models.CharField(max_length=100)
    room = models.ForeignKey("Room", on_delete=models.CASCADE, null=True, blank=True, related_name="seasons")
    room_type = models.CharField(max_length=20, choices=Room.Type.choices, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    apply_on = models.CharField(max_length=10, choices=ApplyOn.choices, default=ApplyOn.ALL)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["start_date"]
        verbose_name = "Rate season"
        verbose_name_plural = "Rate seasons"

    def __str__(self) -> str:  # pragma: no cover
        target = self.room or self.get_room_type_display() or "All"
        return f"{self.name} • {target} • {self.start_date} → {self.end_date} • {self.get_apply_on_display()}"

    def clean(self):
        # Must specify at least one target
        if not self.room and not self.room_type:
            raise ValidationError("Select a room or a room type.")
        if self.start_date >= self.end_date:
            raise ValidationError({"end_date": "End date must be after start date."})


class Client(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    document_id = models.CharField("ID/Passport", max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

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
    # Breakfast options
    breakfast_included = models.BooleanField(default=False)
    breakfast_price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))

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
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        TRANSFER = "transfer", "Bank Transfer"

    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name="invoice")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="invoices")
    # Legal/compliance fields
    series = models.CharField(max_length=10, default="XB")
    number = models.PositiveIntegerField(blank=True, null=True)
    issue_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(blank=True, null=True)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)

    # Totals and misc
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="EUR")
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-issue_date"]
        constraints = [
            models.UniqueConstraint(fields=["series", "number"], name="uniq_invoice_series_number"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        label = f"{self.series}-{self.number}" if self.number else f"#{self.pk or 'new'}"
        return f"Invoice {label} for {self.client} ({self.total} {self.currency})"

    def assign_sequential_number(self):
        """
        Assign next sequential number within the same series if number is empty.
        """
        if self.number is None:
            last = Invoice.objects.filter(series=self.series).aggregate(models.Max("number"))["number__max"] or 0
            self.number = int(last) + 1

    def build_default_lines(self, overwrite: bool = False):
        """
        Build invoice lines from reservation:
        - One line per night with nightly price (accommodation).
        - One line per night for breakfast if included and price > 0.
        """
        if not overwrite and self.lines.exists():
            return
        if overwrite:
            self.lines.all().delete()

        res = self.reservation
        start = res.check_in
        nights = res.nights
        for i in range(nights):
            day = start + timedelta(days=i)
            price = res.room.get_price_for_date(day)
            InvoiceLine.objects.create(
                invoice=self,
                description=f"Accommodation {res.room.number} — {day.isoformat()}",
                quantity=Decimal("1.00"),
                unit_price=price,
                vat_rate=Decimal("9.00"),  # set per your jurisdiction
            )
            if res.breakfast_included and res.breakfast_price and res.breakfast_price > 0:
                InvoiceLine.objects.create(
                    invoice=self,
                    description=f"Breakfast — {day.isoformat()}",
                    quantity=Decimal("1.00"),
                    unit_price=res.breakfast_price,
                    vat_rate=Decimal("9.00"),  # set per your jurisdiction
                )

    def get_vat_summary(self) -> list[dict]:
        """
        Return a list of dicts: [{'vat_rate': Decimal, 'base': Decimal, 'vat': Decimal, 'total': Decimal}, ...]
        """
        summary: dict[Decimal, dict] = {}
        for line in self.lines.all():
            r = line.vat_rate
            if r not in summary:
                summary[r] = {"vat_rate": r, "base": Decimal("0.00"), "vat": Decimal("0.00"), "total": Decimal("0.00")}
            summary[r]["base"] += line.total_excl_vat
            summary[r]["vat"] += line.vat_amount
            summary[r]["total"] += line.total
        # Quantize
        for v in summary.values():
            v["base"] = v["base"].quantize(Decimal("0.01"))
            v["vat"] = v["vat"].quantize(Decimal("0.01"))
            v["total"] = v["total"].quantize(Decimal("0.01"))
        return sorted(summary.values(), key=lambda x: x["vat_rate"])

    def compute_total(self) -> Decimal:
        total = Decimal("0.00")
        for line in self.lines.all():
            total += line.total
        return total.quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        creating = self.pk is None
        # Default due date to today if missing; adjust as needed (e.g., +5/14 days)
        if self.due_date is None:
            try:
                self.due_date = timezone.localdate()
            except Exception:
                self.due_date = date.today()
        # Ensure we have a number
        self.assign_sequential_number()
        super().save(*args, **kwargs)

        # On creation, generate default lines if none exist
        if creating and not self.lines.exists():
            self.build_default_lines(overwrite=True)

        # Update total from lines
        new_total = self.compute_total()
        if new_total != self.total:
            Invoice.objects.filter(pk=self.pk).update(total=new_total)
            self.total = new_total  # keep instance in sync

    def as_dict(self) -> dict:
        return {
            "invoice_id": self.pk,
            "series": self.series,
            "number": self.number,
            "issue_date": self.issue_date,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "client": f"{self.client.first_name} {self.client.last_name}",
            "room": f"{self.reservation.room.number} - {self.reservation.room.get_type_display()}",
            "check_in": self.reservation.check_in.isoformat(),
            "check_out": self.reservation.check_out.isoformat(),
            "nights": self.reservation.nights,
            "currency": self.currency,
            "total": str(self.total),
            "vat_summary": [
                {
                    "vat_rate": str(item["vat_rate"]),
                    "base": str(item["base"]),
                    "vat": str(item["vat"]),
                    "total": str(item["total"]),
                }
                for item in self.get_vat_summary()
            ],
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


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    vat_rate = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.00"))  # e.g., 19.00, 9.00
    total_excl_vat = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["id"]

    def __str__(self):  # pragma: no cover
        return f"{self.description} x {self.quantity} @ {self.unit_price}"

    def compute(self):
        base = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        vat = (base * self.vat_rate / Decimal("100")).quantize(Decimal("0.01"))
        total = (base + vat).quantize(Decimal("0.01"))
        return base, vat, total

    def save(self, *args, **kwargs):
        base, vat, total = self.compute()
        self.total_excl_vat = base
        self.vat_amount = vat
        self.total = total
        super().save(*args, **kwargs)


class NightAudit(models.Model):
    """
    End-of-day snapshot (night audit) with key metrics stored as JSON.
    """
    date = models.DateField(unique=True)
    closed_at = models.DateTimeField(auto_now_add=True)
    totals = models.JSONField(default=dict)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self) -> str:  # pragma: no cover
        return f"Night Audit {self.date}"
