from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from accounts.models import User
from .models import Business, Client


class ClientAPITestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='password')
        self.other_user = User.objects.create_user(username='other', email='other@example.com', password='password')
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.user)
        self.business = Business.objects.create(name='Test Business', created_by=self.user)

    def test_create_client(self):
        payload = {
            'business': self.business.id,
            'name': 'Acme Corp',
            'email': 'acme@example.com',
            'phone': '1234567890'
        }
        response = self.client_api.post('/api/clients/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Client.objects.count(), 1)
        client = Client.objects.first()
        self.assertEqual(client.name, 'Acme Corp')

    def test_list_clients(self):
        Client.objects.create(business=self.business, name='Client A')
        Client.objects.create(business=self.business, name='Client B')
        response = self.client_api.get('/api/clients/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_cannot_create_for_other_business(self):
        other_business = Business.objects.create(name='Other Biz', created_by=self.other_user)
        payload = {'business': other_business.id, 'name': 'Evil Client'}
        response = self.client_api.post('/api/clients/', payload, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Client.objects.count(), 0)
