from rest_framework import serializers
from django.db import transaction
from .models import Invoice, InvoiceLineItem, Receipt


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = '__all__'
        # invoice is set by the parent serializer's create() method; mark as read-only
        read_only_fields = ('invoice', 'total_price',)


class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True)
    business_name = serializers.CharField(source='business.name', read_only=True)
    business_address = serializers.CharField(source='business.address', read_only=True)
    business_email = serializers.CharField(source='business.email', read_only=True)
    business_phone = serializers.CharField(source='business.phone_number', read_only=True)

    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at', 'subtotal', 'tax_amount', 'total_amount', 'invoice_number')

    def generate_invoice_number(self):
        """Generate a unique invoice number within a transaction to prevent race conditions."""
        with transaction.atomic():
            # Lock the table to prevent other transactions from reading until this one is done.
            last_invoice = Invoice.objects.select_for_update().order_by('-id').first()
            if last_invoice and last_invoice.invoice_number and last_invoice.invoice_number.startswith('INV-'):
                try:
                    last_number = int(last_invoice.invoice_number.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1 # Fallback if parsing fails
            else:
                new_number = 1 # First invoice
            
            invoice_number = f'INV-{new_number:04d}'
            return invoice_number

    def create(self, validated_data, **kwargs):
        # created_by may be passed either as kwarg to save or included in validated_data by DRF
        created_by = kwargs.pop('created_by', None) or validated_data.pop('created_by', None)

        # Pop line items safely; validate presence
        line_items_data = validated_data.pop('line_items', None)
        if not line_items_data or not isinstance(line_items_data, list) or len(line_items_data) == 0:
            raise serializers.ValidationError({
                'line_items': ['At least one line item is required.']
            })

        # Attach generated fields and created_by
        validated_data['invoice_number'] = self.generate_invoice_number()
        if created_by is not None:
            validated_data['created_by'] = created_by

        # Create invoice
        try:
            invoice = Invoice.objects.create(**validated_data)
        except Exception as e:
            # Bubble up a readable validation error instead of crashing
            raise serializers.ValidationError({'non_field_errors': [str(e)]})
        # Create line items, computing total_price and validating values
        for item_data in line_items_data:
            try:
                quantity = int(item_data.get('quantity', 0))
                unit_price = float(item_data.get('unit_price', 0))
                total_price = quantity * unit_price
            except Exception:
                # Clean up created invoice on invalid line item data
                invoice.delete()
                raise serializers.ValidationError({
                    'line_items': ['Invalid line item data (quantity and unit_price are required and must be numbers).']
                })

            InvoiceLineItem.objects.create(
                invoice=invoice,
                description=item_data.get('description', ''),
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price
            )

        # Calculate invoice totals
        invoice.calculate_totals()

        return invoice
    
    def update(self, instance, validated_data):
        line_items_data = validated_data.pop('line_items', None)
        
        # Update invoice fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Handle line items if provided
        if line_items_data is not None:
            # Delete existing line items
            instance.line_items.all().delete()
            
            # Create new line items
            for item_data in line_items_data:
                # Calculate total price for each line item
                item_data['total_price'] = item_data['quantity'] * item_data['unit_price']
                InvoiceLineItem.objects.create(invoice=instance, **item_data)
        
        # Calculate invoice totals
        instance.calculate_totals()
        instance.save()
        
        return instance


class DashboardSummarySerializer(serializers.Serializer):
    total_invoices = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    pending_invoices = serializers.IntegerField()
    paid_invoices = serializers.IntegerField()
    overdue_invoices = serializers.IntegerField()


class ReportSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    status = serializers.CharField(required=False)
    business_id = serializers.IntegerField(required=False)


class FinancialReportSerializer(serializers.Serializer):
    period = serializers.CharField()
    revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    invoices_count = serializers.IntegerField()


class InvoiceReportSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)

    class Meta:
        model = Invoice
        fields = (
            'id', 'invoice_number', 'client_name', 'business_name',
            'issue_date', 'due_date', 'status', 'total_amount'
        )


class ReceiptSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    client_name = serializers.CharField(source='invoice.client_name', read_only=True)
    business_name = serializers.CharField(source='invoice.business.name', read_only=True)
    currency = serializers.CharField(source='invoice.currency', read_only=True)
    line_items = InvoiceLineItemSerializer(source='invoice.line_items', many=True, read_only=True)

    class Meta:
        model = Receipt
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at', 'receipt_number')

    def generate_receipt_number(self):
        """Generate a unique receipt number within a transaction to prevent race conditions."""
        with transaction.atomic():
            # Lock the table to prevent other transactions from reading until this one is done.
            last_receipt = Receipt.objects.select_for_update().order_by('-id').first()
            if last_receipt and last_receipt.receipt_number and last_receipt.receipt_number.startswith('REC-'):
                try:
                    last_number = int(last_receipt.receipt_number.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1 # Fallback if parsing fails
            else:
                new_number = 1 # First receipt
            
            receipt_number = f'REC-{new_number:04d}'
            return receipt_number

    def create(self, validated_data):
        # Generate receipt number
        validated_data['receipt_number'] = self.generate_receipt_number()
        return super().create(validated_data)


class RecurringInvoiceSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)

    class Meta:
        model = None
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'last_generated_at')

    def to_representation(self, instance):
        from .models import RecurringInvoice
        self.Meta.model = RecurringInvoice
        return super().to_representation(instance)

    def create(self, validated_data):
        if not validated_data.get('next_run_date'):
            validated_data['next_run_date'] = validated_data.get('start_date')
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class ReminderRuleSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)

    class Meta:
        model = None
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'last_sent')

    def to_representation(self, instance):
        from .models import ReminderRule
        self.Meta.model = ReminderRule
        return super().to_representation(instance)
