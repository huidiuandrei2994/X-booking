from __future__ import annotations

from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView
from django.forms import inlineformset_factory

from .models import Invoice, InvoiceLine
from .forms import InvoiceForm, InvoiceLineForm


class InvoiceUpdateView(TemplateView):
    template_name = "hotellapp/invoice_form.html"

    def get_object(self) -> Invoice:
        return get_object_or_404(Invoice, pk=self.kwargs["pk"])

    def _get_formset_class(self):
        return inlineformset_factory(
            Invoice,
            InvoiceLine,
            form=InvoiceLineForm,
            extra=1,
            can_delete=True,
            fields=("description", "quantity", "unit_price", "vat_rate"),
        )

    def get(self, request, *args, **kwargs):
        invoice = self.get_object()
        form = InvoiceForm(instance=invoice)
        Formset = self._get_formset_class()
        formset = Formset(instance=invoice)
        return self.render_to_response({"form": form, "formset": formset, "invoice": invoice})

    def post(self, request, *args, **kwargs):
        invoice = self.get_object()
        form = InvoiceForm(request.POST, instance=invoice)
        Formset = self._get_formset_class()
        formset = Formset(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            # Recompute totals after line changes
            invoice.refresh_from_db()
            invoice.save()  # will recompute total in model logic
            return redirect(reverse("invoice_detail", args=[invoice.pk]))
        return self.render_to_response({"form": form, "formset": formset, "invoice": invoice})
