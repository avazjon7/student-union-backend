from django.urls import path

from .views_public import EventListView, EventDetailView, SeatGroupListView
from .views_student import (
    EventRegisterView,
    MyRegistrationsView,
    MyTicketsView,
    SeatListByGroupView,
)
from .views_checkin import CheckInView

urlpatterns = [
    path("events/", EventListView.as_view(), name="events-list"),
    path("events/<slug:slug>/", EventDetailView.as_view(), name="event-detail"),
    path("events/<slug:slug>/register/", EventRegisterView.as_view(), name="event-register"),

    path("events/<int:event_id>/seat-groups/", SeatGroupListView.as_view(), name="seat-groups"),
    path("seat-groups/<int:group_id>/seats/", SeatListByGroupView.as_view(), name="seats-by-group"),

    path("my/registrations/", MyRegistrationsView.as_view(), name="my-registrations"),
    path("my/tickets/", MyTicketsView.as_view(), name="my-tickets"),

    path("checkin/", CheckInView.as_view(), name="checkin"),
]
