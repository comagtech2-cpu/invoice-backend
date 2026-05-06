from django.urls import path
from .views import BusinessListCreateView, BusinessDetailView, ClientListCreateView, ClientDetailView

urlpatterns = [
    path('businesses/', BusinessListCreateView.as_view(), name='business-list-create'),
    path('businesses/<int:pk>/', BusinessDetailView.as_view(), name='business-detail'),

    # Client endpoints
    path('clients/', ClientListCreateView.as_view(), name='client-list-create'),
    path('clients/<int:pk>/', ClientDetailView.as_view(), name='client-detail'),
]