from rest_framework import serializers
from .models import Business, Client


class BusinessSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Business
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at')

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if obj.logo:
            try:
                url = obj.logo.url
            except ValueError:
                return None
            if request:
                return request.build_absolute_uri(url)
            return url
        return None


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')