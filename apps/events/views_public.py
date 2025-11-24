from rest_framework import generics
from .models import Event, SeatGroup, SeatStatus
from .serializers import EventSerializer, SeatGroupSerializer


class EventListView(generics.ListAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        qs = Event.objects.filter(is_active=True)
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__slug=category)
        return qs.order_by("start_at")


class EventDetailView(generics.RetrieveAPIView):
    queryset = Event.objects.filter(is_active=True)
    serializer_class = EventSerializer
    lookup_field = "slug"


class SeatGroupListView(generics.ListAPIView):
    """
    GET /api/events/<event_id>/seat-groups/
    """

    serializer_class = SeatGroupSerializer

    def get_queryset(self):
        event_id = self.kwargs["event_id"]
        qs = (
            SeatGroup.objects.filter(event_id=event_id)
            .order_by("id")
            .prefetch_related("seats")
        )

        # добавляем free_seats аннотацией
        from django.db.models import Count, Q

        qs = qs.annotate(
            free_seats=Count("seats", filter=Q(seats__status=SeatStatus.FREE))
        )
        return qs
