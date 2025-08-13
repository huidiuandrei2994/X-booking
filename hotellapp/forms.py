from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import Room, Client, Reservation


class BootstrapFormMixin:
    """
    Apply Bootstrap styles to Django form fields automatically.
    """
    def _bootstrapify(self):
        for name, field in self.fields.items():
            widget = field.widget
            existing = widget.attrs.get("class", "").strip()

            # Style checkbox and radio as well, to keep consistent theming
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = f"{existing} form-check-input".strip()
                continue
            if isinstance(widget, forms.RadioSelect):
                widget.attrs["class"] = f"{existing} form-check-input".strip()
                continue

            # Selects vs. other inputs
            base_class = "form-select" if isinstance(widget, forms.Select) else "form-control"
            widget.attrs["class"] = f"{existing} {base_class}".strip()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bootstrapify()


class RoomForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Room
        fields = ["number", "type", "price_per_night", "status"]


class ClientForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "first_name", "last_name",
            "email", "phone",
            "address", "city", "country",
            "date_of_birth", "document_id", "notes",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class ReservationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ["client", "room", "check_in", "check_out", "breakfast_included", "breakfast_price"]

        widgets = {
            "check_in": forms.DateInput(attrs={"type": "date"}),
            "check_out": forms.DateInput(attrs={"type": "date"}),
            "breakfast_price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def clean(self):
        cleaned = super().clean()
        # Delegate to model validation for overlap; capture to form errors nicely
        instance = Reservation(
            client=cleaned.get("client"),
            room=cleaned.get("room"),
            check_in=cleaned.get("check_in"),
            check_out=cleaned.get("check_out"),
        )
        try:
            instance.clean()
        except ValidationError as e:
            self.add_error(None, e)
        return cleaned


# -------- Invoices --------
from .models import Invoice, InvoiceLine  # noqa: E402 (placed after other imports for patch simplicity)


class InvoiceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["series", "number", "due_date", "payment_method", "currency", "notes"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class InvoiceLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = InvoiceLine
        fields = ["description", "quantity", "unit_price", "vat_rate"]
        widgets = {
            "quantity": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "unit_price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "vat_rate": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }
