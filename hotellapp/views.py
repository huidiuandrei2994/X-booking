from __future__ import annotations

from datetime import date, timedelta
import csv

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DetailView, View, TemplateView, DeleteView
from django.db.models.deletion import ProtectedError
from django.db import models

from . import models
from .forms import RoomForm, ClientForm, ReservationForm
from .models import Room, Client, Reservation, Invoice
from .presenters import ReservationPresenter


class CalendarView(TemplateView):
    template_name = "hotellapp/calendar.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Parameters
        start_str = self.request.GET.get("start")
        try:
            start = date.fromisoformat(start_str) if start_str else timezone.localdate()
        except ValueError:
            start = timezone.localdate()

        try:
            days = int(self.request.GET.get("days", "14"))
        except ValueError:
            days = 14
        if days not in (7, 14, 30):
            days = 14

        end = start + timedelta(days=days)
        day_list = [start + timedelta(i) for i in range(days)]

        # Pull rooms and overlapping reservations
        rooms = list(Room.objects.order_by("number"))
        res_qs = (
            Reservation.objects.select_related("client", "room")
            .filter(
                status__in=[Reservation.Status.BOOKED, Reservation.Status.CHECKED_IN],
                check_in__lt=end,
                check_out__gt=start,
            )
            .order_by("room__number", "check_in")
        )

        # Group reservations by room id
        by_room = {}
        for r in res_qs:
            by_room.setdefault(r.room_id, []).append(r)

        rooms_data = []
        for room in rooms:
            blocks = []
            for r in by_room.get(room.id, []):
                b_start = max(r.check_in, start)
                b_end = min(r.check_out, end)
                start_idx = (b_start - start).days
                span = (b_end - b_start).days
                if span <= 0:
                    continue
                label = f"{r.client.first_name} {r.client.last_name}".strip()
                blocks.append(
                    {
                        "start_idx": start_idx,
                        "span": span,
                        "label": label,
                        "status": r.status,
                        "reservation_id": r.id,
                    }
                )
            # Build row cells with colspans
            cells = []
            cursor = 0
            for b in sorted(blocks, key=lambda x: x["start_idx"]):
                if b["start_idx"] > cursor:
                    # empty gap
                    gap = b["start_idx"] - cursor
                    cells.append({"type": "empty", "span": gap})
                    cursor = b["start_idx"]
                cells.append({"type": "block", **b})
                cursor += b["span"]
            if cursor < days:
                cells.append({"type": "empty", "span": days - cursor})
            rooms_data.append({"room": room, "cells": cells})

        # Daily occupancy across all rooms
        rooms_count = len(rooms) or 1
        occupancy = []
        for d in day_list:
            active_rooms = set()
            for r in res_qs:
                if r.check_in <= d < r.check_out:
                    active_rooms.add(r.room_id)
            count = len(active_rooms)
            percent = int(round(count / rooms_count * 100))
            occupancy.append({"count": count, "percent": percent})

        ctx.update(
            {
                "start": start,
                "days": days,
                "dates": [{"d": d, "dow": d.strftime("%a")} for d in day_list],
                "rooms_data": rooms_data,
                "prev_start": start - timedelta(days=days),
                "next_start": start + timedelta(days=days),
                "occupancy": occupancy,
                "rooms_count": len(rooms),
            }
        )
        return ctx


# Rooms
class RoomListView(ListView):
    model = Room
    template_name = "hotellapp/room_list.html"
    context_object_name = "rooms"


class RoomCreateView(CreateView):
    model = Room
    form_class = RoomForm
    template_name = "hotellapp/room_form.html"
    success_url = reverse_lazy("room_list")


class RoomUpdateView(UpdateView):
    model = Room
    form_class = RoomForm
    template_name = "hotellapp/room_form.html"
    success_url = reverse_lazy("room_list")


class RoomDeleteView(DeleteView):
    model = Room
    template_name = "hotellapp/room_confirm_delete.html"
    success_url = reverse_lazy("room_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            return super().delete(request, *args, **kwargs)
        except ProtectedError:
            messages.error(request, "Cannot delete room with existing reservations.")
            return redirect("room_list")


# Clients
class ClientListView(ListView):
    model = Client
    template_name = "hotellapp/client_list.html"
    context_object_name = "clients"


class ClientCreateView(CreateView):
    model = Client
    form_class = ClientForm
    template_name = "hotellapp/client_form.html"
    success_url = reverse_lazy("client_list")


class ClientUpdateView(UpdateView):
    model = Client
    form_class = ClientForm
    template_name = "hotellapp/client_form.html"
    success_url = reverse_lazy("client_list")


class ClientDeleteView(DeleteView):
    model = Client
    template_name = "hotellapp/client_confirm_delete.html"
    success_url = reverse_lazy("client_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            return super().delete(request, *args, **kwargs)
        except ProtectedError:
            messages.error(request, "Cannot delete client with existing reservations or invoices.")
            return redirect("client_list")


# Reservations
class ReservationListView(ListView):
    model = Reservation
    template_name = "hotellapp/reservation_list.html"
    context_object_name = "reservations"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("client", "room")
        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status")
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")
        if q:
            qs = qs.filter(
                models.Q(client__first_name__icontains=q)
                | models.Q(client__last_name__icontains=q)
                | models.Q(room__number__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        if start:
            try:
                qs = qs.filter(check_out__gte=date.fromisoformat(start))
            except ValueError:
                pass
        if end:
            try:
                qs = qs.filter(check_in__lte=date.fromisoformat(end))
            except ValueError:
                pass
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter"] = {
            "q": self.request.GET.get("q", ""),
            "status": self.request.GET.get("status", ""),
            "start": self.request.GET.get("start", ""),
            "end": self.request.GET.get("end", ""),
        }
        return ctx


class ReservationCreateView(CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "hotellapp/reservation_form.html"
    success_url = reverse_lazy("reservation_list")

    def get_initial(self):
        initial = super().get_initial()
        check_in = self.request.GET.get("check_in")
        check_out = self.request.GET.get("check_out")
        client = self.request.GET.get("client")
        room = self.request.GET.get("room")
        if check_in:
            initial["check_in"] = check_in
        if check_out:
            initial["check_out"] = check_out
        if client:
            initial["client"] = client
        if room:
            initial["room"] = room
        return initial

    def form_valid(self, form):
        presenter = ReservationPresenter()
        presenter.create_reservation(self.request, form)
        return HttpResponseRedirect(self.get_success_url())


class ReservationUpdateView(UpdateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "hotellapp/reservation_form.html"
    success_url = reverse_lazy("reservation_list")


class ReservationDeleteView(DeleteView):
    model = Reservation
    template_name = "hotellapp/reservation_confirm_delete.html"
    success_url = reverse_lazy("reservation_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            return super().delete(request, *args, **kwargs)
        except ProtectedError:
            messages.error(request, "Cannot delete reservation that is referenced by other records.")
            return redirect("reservation_list")


# Workflow actions
class ReservationCheckInView(View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        reservation = get_object_or_404(Reservation, pk=pk)
        ReservationPresenter().check_in(request, reservation)
        return redirect("reservation_list")


class ReservationCheckOutView(View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        reservation = get_object_or_404(Reservation, pk=pk)
        ReservationPresenter().check_out(request, reservation)
        return redirect("reservation_list")


class ReservationCancelView(View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        reservation = get_object_or_404(Reservation, pk=pk)
        ReservationPresenter().cancel(request, reservation)
        return redirect("reservation_list")


class RoomMarkCleanedView(View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        room = get_object_or_404(Room, pk=pk)
        ReservationPresenter().mark_room_cleaned(request, room)
        return redirect("room_list")


# Invoices
class InvoiceListView(ListView):
    model = Invoice
    template_name = "hotellapp/invoice_list.html"
    context_object_name = "invoices"


class InvoiceDetailView(DetailView):
    model = Invoice
    template_name = "hotellapp/invoice_detail.html"
    context_object_name = "invoice"


class InvoicePrintView(DetailView):
    model = Invoice
    template_name = "hotellapp/invoice_pdf.html"
    context_object_name = "invoice"


class InvoicesCsvExportView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="invoices.csv"'
        writer = csv.writer(response)
        writer.writerow(
            ["ID", "Issue Date", "Client", "Room", "Check-in", "Check-out", "Nights", "Price/night", "Total",
             "Currency"])
        qs = Invoice.objects.select_related("client", "reservation__room").order_by("-issue_date")
        for inv in qs:
            r = inv.reservation
            writer.writerow([
                inv.id,
                inv.issue_date,
                f"{inv.client.first_name} {inv.client.last_name}",
                f"{r.room.number}",
                r.check_in,
                r.check_out,
                r.nights,
                r.room.price_per_night,
                inv.total,
                inv.currency,
            ])
        return response


# API
class AvailabilityAPI(View):
    """
    Returns JSON list of available rooms for a given date range and optional type.
    GET params: start=YYYY-MM-DD, end=YYYY-MM-DD, type=<Room.Type value>
    """

    def get(self, request: HttpRequest) -> JsonResponse:
        start_s = request.GET.get("start")
        end_s = request.GET.get("end")
        room_type = request.GET.get("type")
        try:
            start = date.fromisoformat(start_s) if start_s else None
            end = date.fromisoformat(end_s) if end_s else None
        except ValueError:
            return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)
        if not start or not end or not (start < end):
            return JsonResponse({"error": "Provide valid start and end dates (start < end)."}, status=400)

        overlapping = Reservation.objects.filter(
            status__in=[Reservation.Status.BOOKED, Reservation.Status.CHECKED_IN],
            check_in__lt=end,
            check_out__gt=start,
        ).values_list("room_id", flat=True)

        rooms_qs = Room.objects.exclude(id__in=overlapping)
        if room_type:
            rooms_qs = rooms_qs.filter(type=room_type)

        rooms = [
            {"id": r.id, "number": r.number, "type": r.type, "price_per_night": str(r.price_per_night),
             "status": r.status}
            for r in rooms_qs.order_by("number")
        ]
        return JsonResponse({"start": start.isoformat(), "end": end.isoformat(), "rooms": rooms})
