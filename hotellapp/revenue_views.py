from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from django.views.generic import TemplateView
from django.db.models import Sum
from django.db.models.functions import TruncDate

from .models import Invoice, Reservation


class ReportRevenueView(TemplateView):
    template_name = "hotellapp/report_revenue.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Parse date range with safe fallbacks (last 30 days by default)
        today = date.today()
        default_start = today - timedelta(days=29)
        start_str = (self.request.GET.get("start") or "").strip()
        end_str = (self.request.GET.get("end") or "").strip()

        def parse_iso(s: str, default: date) -> date:
            try:
                return date.fromisoformat(s) if s else default
            except Exception:
                return default

        start = parse_iso(start_str, default_start)
        end = parse_iso(end_str, today)

        qs = Invoice.objects.filter(issue_date__date__gte=start, issue_date__date__lte=end)

        # Group by calendar day and sum totals
        rows = (
            qs.annotate(day=TruncDate("issue_date"))
            .values("day")
            .order_by("day")
            .annotate(total=Sum("total"))
        )

        data = [{"date": r["day"], "total": r["total"]} for r in rows]
        grand_total = qs.aggregate(total=Sum("total"))["total"] or Decimal("0.00")

        ctx.update(
            {
                "start": start,
                "end": end,
                "data": data,
                "grand_total": grand_total,
            }
        )
        return ctx


class ReportKPIView(TemplateView):
    """
    KPI report with ADR (Average Daily Rate) and Avg LOS (Length of Stay)
    computed over a selected period.

    Definitions:
    - nights_sold: room-nights within [start, end] from non-canceled reservations
    - accommodation_revenue: sum of nightly prices (seasons applied) for those nights
    - ADR = accommodation_revenue / nights_sold
    - arrivals: reservations with check_in in [start, end] and not canceled
    - avg_los = average nights for these arrivals
    """
    template_name = "hotellapp/report_kpi.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Parse date range (default: last 30 days)
        today = date.today()
        default_start = today - timedelta(days=29)
        start_str = (self.request.GET.get("start") or "").strip()
        end_str = (self.request.GET.get("end") or "").strip()

        def parse_iso(s: str, default: date) -> date:
            try:
                return date.fromisoformat(s) if s else default
            except Exception:
                return default

        start = parse_iso(start_str, default_start)
        end = parse_iso(end_str, today)
        end_exclusive = end + timedelta(days=1)

        # Consider active/non-canceled reservations only
        active_statuses = [
            Reservation.Status.BOOKED,
            Reservation.Status.CHECKED_IN,
            Reservation.Status.CHECKED_OUT,
        ]

        # Nights sold and accommodation revenue (per-night prices)
        overlaps = (
            Reservation.objects.select_related("room", "client")
            .filter(status__in=active_statuses, check_in__lt=end_exclusive, check_out__gt=start)
        )

        nights_sold = 0
        accommodation_revenue = Decimal("0.00")

        for res in overlaps:
            cur_start = max(res.check_in, start)
            cur_end = min(res.check_out, end_exclusive)
            days = (cur_end - cur_start).days
            for i in range(days):
                day = cur_start + timedelta(days=i)
                price = res.room.get_price_for_date(day)
                accommodation_revenue += price
                nights_sold += 1

        accommodation_revenue = accommodation_revenue.quantize(Decimal("0.01"))
        adr = (accommodation_revenue / nights_sold).quantize(Decimal("0.01")) if nights_sold else Decimal("0.00")

        # Arrivals and average length of stay
        arrivals_qs = Reservation.objects.filter(
            status__in=active_statuses,
            check_in__gte=start,
            check_in__lte=end,
        ).only("check_in", "check_out")
        arrivals = arrivals_qs.count()
        total_los_nights = 0
        for r in arrivals_qs:
            total_los_nights += max(0, (r.check_out - r.check_in).days)
        avg_los = (Decimal(total_los_nights) / Decimal(arrivals)).quantize(Decimal("0.01")) if arrivals else Decimal("0.00")

        ctx.update(
            {
                "start": start,
                "end": end,
                "nights_sold": nights_sold,
                "accommodation_revenue": accommodation_revenue,
                "adr": adr,
                "arrivals": arrivals,
                "avg_los": avg_los,
            }
        )
        return ctx
