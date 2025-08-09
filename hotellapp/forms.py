from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import Room, Client, Reservation


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["number", "type", "price_per_night", "status"]


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["first_name", "last_name", "email", "phone"]


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ["client", "room", "check_in", "check_out"]

        widgets = {
            "check_in": forms.DateInput(attrs={"type": "date"}),
            "check_out": forms.DateInput(attrs={"type": "date"}),
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
