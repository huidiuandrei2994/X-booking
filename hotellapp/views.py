from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import csv

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, DetailView, View, TemplateView, DeleteView
from django.db.models.deletion import ProtectedError
from django.db import models, transaction

from . import models
from .forms import RoomForm, ClientForm, ReservationForm
from .models import Room, Client, Reservation, Invoice, NightAudit
from .presenters import ReservationPresenter


class CalendarView(TemplateView):
    template_name = "hotellapp/calendar_ui.html"

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
        # Important: set self.object for SuccessUrlMixin to avoid AttributeError
        self.object = presenter.create_reservation(self.request, form)
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
@method_decorator(login_required, name="dispatch")
class ReservationCheckInView(View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        reservation = get_object_or_404(Reservation, pk=pk)
        ReservationPresenter().check_in(request, reservation)
        return redirect("reservation_list")


@method_decorator(login_required, name="dispatch")
class ReservationCheckOutView(View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        reservation = get_object_or_404(Reservation, pk=pk)
        ReservationPresenter().check_out(request, reservation)
        return redirect("reservation_list")


@method_decorator(login_required, name="dispatch")
class ReservationCancelView(View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        reservation = get_object_or_404(Reservation, pk=pk)
        ReservationPresenter().cancel(request, reservation)
        return redirect("reservation_list")


@method_decorator(login_required, name="dispatch")
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


@method_decorator(login_required, name="dispatch")
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


# Reports
class ReportsDashboardView(TemplateView):
    template_name = "hotellapp/reports_dashboard.html"


class ReportOccupancyView(TemplateView):
    template_name = "hotellapp/report_occupancy.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        start_str = self.request.GET.get("start")
        end_str = self.request.GET.get("end")
        try:
            start = date.fromisoformat(start_str) if start_str else timezone.localdate()
        except ValueError:
            start = timezone.localdate()
        try:
            end = date.fromisoformat(end_str) if end_str else start + timedelta(days=14)
        except ValueError:
            end = start + timedelta(days=14)
        if end <= start:
            end = start + timedelta(days=1)

        day_list = [start + timedelta(i) for i in range((end - start).days)]
        rooms = list(Room.objects.all())
        res_qs = Reservation.objects.filter(
            status__in=[Reservation.Status.BOOKED, Reservation.Status.CHECKED_IN],
            check_in__lt=end,
            check_out__gt=start,
        )
        rooms_count = len(rooms) or 1
        occupancy = []
        for d in day_list:
            active_rooms = res_qs.filter(check_in__lte=d, check_out__gt=d).values_list("room_id", flat=True).distinct()
            count = active_rooms.count()
            percent = int(round(count / rooms_count * 100))
            occupancy.append({"date": d, "count": count, "percent": percent})

        ctx.update({"start": start, "end": end, "days": day_list, "occupancy": occupancy, "rooms_count": len(rooms)})
        return ctx


class ReportRevenueView(TemplateView):
    template_name = "hotellapp/report_revenue.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        end_default = timezone.localdate()
        start_default = end_default - timedelta(days=30)
        start_str = self.request.GET.get("start")
        end_str = self.request.GET.get("end")
        try:
            start = date.fromisoformat(start_str) if start_str else start_default
        except ValueError:
            start = start_default
        try:
            end = date.fromisoformat(end_str) if end_str else end_default
        except ValueError:
            end = end_default
        if end < start:
            start, end = end, start

        # Group totals by day
        totals = (
            Invoice.objects.filter(issue_date__date__gte=start, issue_date__date__lte=end)
            .values("issue_date__date")
            .order_by("issue_date__date")
            .annotate(total=models.Sum("total"))
        )
        by_day = {row["issue_date__date"]: row["total"] for row in totals}
        day_list = [start + timedelta(i) for i in range((end - start).days + 1)]
        data = [{"date": d, "total": by_day.get(d, 0)} for d in day_list]
        grand_total = sum((row["total"] or 0) for row in data)
        ctx.update({"start": start, "end": end, "data": data, "grand_total": grand_total})
        return ctx


class ReportHousekeepingView(TemplateView):
    template_name = "hotellapp/report_housekeeping.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rooms = Room.objects.order_by("number")
        by_status = {
            "available": rooms.filter(status=Room.Status.AVAILABLE),
            "occupied": rooms.filter(status=Room.Status.OCCUPIED),
            "cleaning": rooms.filter(status=Room.Status.CLEANING),
        }
        counts = {k: qs.count() for k, qs in by_status.items()}
        ctx.update({"by_status": by_status, "counts": counts})
        return ctx

# Night Audit
@method_decorator(login_required, name="dispatch")
class NightAuditPreviewView(TemplateView):
    template_name = "hotellapp/night_audit_preview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        d_str = self.request.GET.get("date")
        try:
            audit_date = date.fromisoformat(d_str) if d_str else timezone.localdate()
        except ValueError:
            audit_date = timezone.localdate()

        rooms_qs = Room.objects.all()
        total_rooms = rooms_qs.count() or 1

        active_qs = Reservation.objects.filter(
            status__in=[Reservation.Status.BOOKED, Reservation.Status.CHECKED_IN],
            check_in__lte=audit_date,
            check_out__gt=audit_date,
        ).select_related("room", "client")

        occupied_rooms_count = active_qs.values("room_id").distinct().count()
        revenue = sum((r.room.get_price_for_date(audit_date) for r in active_qs), start=Decimal("0.00"))
        occupancy_percent = int(round(occupied_rooms_count / total_rooms * 100))
        adr = (revenue / occupied_rooms_count).quantize(Decimal("0.01")) if occupied_rooms_count else Decimal("0.00")
        revpar = (revenue / total_rooms).quantize(Decimal("0.01"))

        arrivals_qs = Reservation.objects.filter(
            check_in=audit_date
        ).exclude(status=Reservation.Status.CANCELED)
        departures_qs = Reservation.objects.filter(
            check_out=audit_date
        ).exclude(status=Reservation.Status.CANCELED)
        stayover_qs = Reservation.objects.filter(
            check_in__lt=audit_date, check_out__gt=audit_date, status__in=[Reservation.Status.BOOKED, Reservation.Status.CHECKED_IN]
        )
        no_show_candidates = Reservation.objects.filter(
            check_in=audit_date, status=Reservation.Status.BOOKED
        )

        existing = NightAudit.objects.filter(date=audit_date).first()

        ctx.update({
            "audit_date": audit_date,
            "occupied_rooms_count": occupied_rooms_count,
            "total_rooms": total_rooms,
            "revenue": revenue,
            "occupancy_percent": occupancy_percent,
            "adr": adr,
            "revpar": revpar,
            "arrivals_count": arrivals_qs.count(),
            "departures_count": departures_qs.count(),
            "stayover_count": stayover_qs.count(),
            "no_shows_count": no_show_candidates.count(),
            "already_closed": bool(existing),
            "arrivals": arrivals_qs.order_by("room__number", "client__last_name")[:20],
            "departures": departures_qs.order_by("room__number", "client__last_name")[:20],
            "stayovers": stayover_qs.order_by("room__number", "client__last_name")[:20],
            "no_shows": no_show_candidates.order_by("room__number", "client__last_name")[:20],
        })
        return ctx


@method_decorator(login_required, name="dispatch")
class NightAuditCloseView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        d_str = request.POST.get("date")
        try:
            audit_date = date.fromisoformat(d_str) if d_str else timezone.localdate()
        except ValueError:
            messages.error(request, "Invalid date.")
            return redirect("night_audit")

        if NightAudit.objects.filter(date=audit_date).exists():
            messages.warning(request, f"Day {audit_date} is already closed.")
            return redirect("night_audit")

        # Compute metrics pre-close
        rooms_qs = Room.objects.all()
        total_rooms = rooms_qs.count() or 1
        active_qs = Reservation.objects.filter(
            status__in=[Reservation.Status.BOOKED, Reservation.Status.CHECKED_IN],
            check_in__lte=audit_date,
            check_out__gt=audit_date,
        ).select_related("room", "client")
        occupied_rooms_count = active_qs.values("room_id").distinct().count()
        revenue = sum((r.room.get_price_for_date(audit_date) for r in active_qs), start=Decimal("0.00"))
        occupancy_percent = int(round(occupied_rooms_count / total_rooms * 100))
        adr = (revenue / occupied_rooms_count).quantize(Decimal("0.01")) if occupied_rooms_count else Decimal("0.00")
        revpar = (revenue / total_rooms).quantize(Decimal("0.01"))

        arrivals_qs = Reservation.objects.filter(check_in=audit_date).exclude(status=Reservation.Status.CANCELED)
        departures_qs = Reservation.objects.filter(check_out=audit_date).exclude(status=Reservation.Status.CANCELED)
        stayover_qs = Reservation.objects.filter(
            check_in__lt=audit_date, check_out__gt=audit_date, status__in=[Reservation.Status.BOOKED, Reservation.Status.CHECKED_IN]
        )
        no_shows_qs = Reservation.objects.filter(check_in=audit_date, status=Reservation.Status.BOOKED)

        from .presenters import ReservationPresenter
        presenter = ReservationPresenter()

        with transaction.atomic():
            # Mark no-shows by canceling remaining booked arrivals
            no_show_count = 0
            for r in no_shows_qs:
                presenter.cancel(request, r)
                no_show_count += 1

            # Recompute cancellations count of the day (including no-shows)
            cancellations_count = Reservation.objects.filter(
                status=Reservation.Status.CANCELED,
                updated_at__date=audit_date,
            ).count()

            totals = {
                "date": audit_date.isoformat(),
                "occupied_rooms": occupied_rooms_count,
                "total_rooms": total_rooms,
                "occupancy_percent": occupancy_percent,
                "revenue": str(revenue),
                "adr": str(adr),
                "revpar": str(revpar),
                "arrivals": arrivals_qs.count(),
                "departures": departures_qs.count(),
                "stayovers": stayover_qs.count(),
                "no_shows": no_show_count,
                "cancellations": cancellations_count,
            }
            NightAudit.objects.create(date=audit_date, totals=totals)

        messages.success(request, f"Night audit completed for {audit_date}.")
        return redirect("night_audit_list")


@method_decorator(login_required, name="dispatch")
class NightAuditListView(ListView):
    model = NightAudit
    template_name = "hotellapp/night_audit_list.html"
    context_object_name = "audits"
    paginate_by = 20


@method_decorator(login_required, name="dispatch")
class NightAuditDetailView(DetailView):
    model = NightAudit
    template_name = "hotellapp/night_audit_detail.html"
    context_object_name = "audit"

@method_decorator(login_required, name="dispatch")
class NightAuditCsvExportView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="night_audit.csv"'
        writer = csv.writer(response)
        writer.writerow(["Date", "Occupancy %", "Occupied", "Total Rooms", "Revenue", "ADR", "RevPAR", "Arrivals", "Departures", "Stayovers", "No-shows", "Cancellations"])
        start_s = request.GET.get("start")
        end_s = request.GET.get("end")
        try:
            start = date.fromisoformat(start_s) if start_s else None
            end = date.fromisoformat(end_s) if end_s else None
        except ValueError:
            start = end = None

        qs = NightAudit.objects.all()
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        qs = qs.order_by("-date")

        for a in qs:
            t = a.totals or {}
            writer.writerow([
                a.date,
                t.get("occupancy_percent", ""),
                t.get("occupied_rooms", ""),
                t.get("total_rooms", ""),
                t.get("revenue", ""),
                t.get("adr", ""),
                t.get("revpar", ""),
                t.get("arrivals", ""),
                t.get("departures", ""),
                t.get("stayovers", ""),
                t.get("no_shows", ""),
                t.get("cancellations", ""),
            ])
        return response

# API
@method_decorator(login_required, name="dispatch")
class ClientQuickCreateAPI(View):
    """
    Quick JSON endpoint to create a Client without leaving the current page.
    Expected POST body (JSON or form-encoded): first_name, last_name (optional), phone (optional), email (optional)
    Returns: {"id": <int>, "name": "First Last"}
    """
    def post(self, request: HttpRequest) -> JsonResponse:
        # Accept JSON or form-encoded
        data = {}
        if request.content_type and "application/json" in request.content_type:
            try:
                import json as _json
                data = _json.loads(request.body.decode() or "{}")
            except Exception:
                return JsonResponse({"error": "Invalid JSON payload."}, status=400)
        else:
            data = request.POST

        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip()

        if not first_name:
            return JsonResponse({"error": "First name is required."}, status=400)

        client = Client.objects.create(
            first_name=first_name,
            last_name=last_name,
            phone=phone or None,
            email=email or None,
        )
        display_name = f"{client.first_name} {client.last_name}".strip()
        return JsonResponse({"id": client.id, "name": display_name}, status=201)


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

        nights = (end - start).days
        rooms = []
        for r in rooms_qs.order_by("number"):
            total = Decimal("0.00")
            for i in range(nights):
                total += r.get_price_for_date(start + timedelta(days=i))
            avg = (total / nights).quantize(Decimal("0.01")) if nights else r.price_per_night
            rooms.append({
                "id": r.id,
                "number": r.number,
                "type": r.type,
                "price_per_night": str(avg),
                "total_price": str(total.quantize(Decimal("0.01"))),
                "status": r.status,
            })
        return JsonResponse({"start": start.isoformat(), "end": end.isoformat(), "rooms": rooms})
