from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from django.views.generic import TemplateView

from .models import Reservation


class ReportBreakfastView(TemplateView):
    template_name = "hotellapp/report_breakfast.html"

    def _parse_date(self, s: str | None) -> date | None:
        if not s:
            return None
        try:
            y, m, d = [int(x) for x in s.split("-")]
            return date(y, m, d)
        except Exception:
            return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        start = self._parse_date(self.request.GET.get("start")) or (today - timedelta(days=14))
        end = self._parse_date(self.request.GET.get("end")) or today
        if end < start:
            start, end = end, start

        # Build day range inclusive [start, end]
        days = []
        d = start
        while d <= end:
            days.append(d)
            d += timedelta(days=1)

        # Reservations overlapping the window with breakfast
        qs = Reservation.objects.filter(
            breakfast_included=True,
            status__in=[
                Reservation.Status.BOOKED,
                Reservation.Status.CHECKED_IN,
                Reservation.Status.CHECKED_OUT,
            ],
            check_in__lt=end + timedelta(days=1),  # overlap condition
            check_out__gt=start,
        ).select_related("room", "client")

        per_day_count: dict[date, int] = {day: 0 for day in days}
        per_day_revenue: dict[date, Decimal] = {day: Decimal("0.00") for day in days}
        by_room: dict[str, dict] = {}
        by_client: dict[str, dict] = {}

        for r in qs:
            # Iterate every night of the reservation intersecting the [start, end] window
            night = max(r.check_in, start)
            last = min(r.check_out, end + timedelta(days=0))
            # Nights are check_in inclusive, check_out exclusive
            while night < min(r.check_out, end + timedelta(days=1)):
                if start <= night <= end:
                    per_day_count[night] += 1
                    per_day_revenue[night] += (r.breakfast_price or Decimal("0.00"))

                    room_key = f"{r.room.number}"
                    rc = by_room.setdefault(room_key, {"room": r.room, "count": 0, "revenue": Decimal("0.00")})
                    rc["count"] += 1
                    rc["revenue"] += (r.breakfast_price or Decimal("0.00"))

                    client_key = f"{r.client.pk}:{r.client.first_name} {r.client.last_name}"
                    cc = by_client.setdefault(client_key, {"client": r.client, "count": 0, "revenue": Decimal("0.00")})
                    cc["count"] += 1
                    cc["revenue"] += (r.breakfast_price or Decimal("0.00"))
                night += timedelta(days=1)

        rows = [
            {
                "date": day,
                "count": per_day_count[day],
                "revenue": per_day_revenue[day].quantize(Decimal("0.01")),
            }
            for day in days
        ]
        total_count = sum(x["count"] for x in rows)
        total_revenue = sum((x["revenue"] for x in rows), Decimal("0.00")).quantize(Decimal("0.01"))

        ctx.update(
            {
                "start": start,
                "end": end,
                "rows": rows,
                "total_count": total_count,
                "total_revenue": total_revenue,
                "by_room": sorted(
                    [
                        {
                            "room": k,
                            "count": v["count"],
                            "revenue": v["revenue"].quantize(Decimal("0.01")),
                        }
                        for k, v in by_room.items()
                    ],
                    key=lambda r: (-r["count"], r["room"]),
                ),
                "by_client": sorted(
                    [
                        {
                            "client": k.split(":", 1)[1],
                            "count": v["count"],
                            "revenue": v["revenue"].quantize(Decimal("0.01")),
                        }
                        for k, v in by_client.items()
                    ],
                    key=lambda r: (-r["count"], r["client"]),
                ),
            }
        )
        return ctx
