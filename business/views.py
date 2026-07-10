from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination
from .models import Business, Client
from .serializers import BusinessSerializer, ClientSerializer


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class BusinessListCreateView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        businesses = Business.objects.filter(created_by=request.user)
        paginator = self.pagination_class()
        paginated_businesses = paginator.paginate_queryset(businesses, request)
        serializer = BusinessSerializer(paginated_businesses, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)
    
    def post(self, request):
        serializer = BusinessSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BusinessDetailView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request, pk):
        try:
            business = Business.objects.get(pk=pk, created_by=request.user)
            serializer = BusinessSerializer(business, context={'request': request})
            return Response(serializer.data)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def put(self, request, pk):
        try:
            business = Business.objects.get(pk=pk, created_by=request.user)
            serializer = BusinessSerializer(business, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def delete(self, request, pk):
        try:
            business = Business.objects.get(pk=pk, created_by=request.user)
            business.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)


class ClientListCreateView(APIView):
    def get(self, request):
        business_id = request.query_params.get('business')
        if business_id:
            clients = Client.objects.filter(business__id=business_id, business__created_by=request.user)
        else:
            clients = Client.objects.filter(business__created_by=request.user)
        serializer = ClientSerializer(clients, many=True)
        return Response(serializer.data)

    def post(self, request):
        business_id = request.data.get('business')
        try:
            business = Business.objects.get(pk=business_id, created_by=request.user)
        except Business.DoesNotExist:
            return Response({'error': 'Business not found or not owned by user'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClientSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(business=business)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClientDetailView(APIView):
    def get(self, request, pk):
        try:
            client = Client.objects.get(pk=pk, business__created_by=request.user)
            serializer = ClientSerializer(client)
            return Response(serializer.data)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            client = Client.objects.get(pk=pk, business__created_by=request.user)
            serializer = ClientSerializer(client, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            client = Client.objects.get(pk=pk, business__created_by=request.user)
            client.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND) 
