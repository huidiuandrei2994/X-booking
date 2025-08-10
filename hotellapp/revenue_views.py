from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from django.views.generic import TemplateView
from django.db.models import Sum
from django.db.models.functions import TruncDate

from .models import Invoice


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
