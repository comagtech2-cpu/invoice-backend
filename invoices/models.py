from django.db import models
from accounts.models import User
from business.models import Business
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    CURRENCY_CHOICES = [
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'British Pound (£)'),
        ('NGN', 'Nigerian Naira (₦)'),
        ('CAD', 'Canadian Dollar (C$)'),
        ('AUD', 'Australian Dollar (A$)'),
        ('JPY', 'Japanese Yen (¥)'),
        ('CHF', 'Swiss Franc (Fr)'),
        ('CNY', 'Chinese Yuan (¥)'),
        ('INR', 'Indian Rupee (₹)'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='invoices')
    client_name = models.CharField(max_length=255)
    client_email = models.EmailField(blank=True, null=True)
    client_address = models.TextField(blank=True, null=True)
    client_phone = models.CharField(max_length=15, blank=True, null=True)
    
    issue_date = models.DateField()
    due_date = models.DateField()
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='NGN')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True, null=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.invoice_number} - {self.client_name}"
    
    def calculate_totals(self):
        """Calculate invoice subtotal, tax amount, and total amount"""
        self.subtotal = sum(item.total_price for item in self.line_items.all())
        self.tax_amount = self.subtotal * (self.tax_rate / 100)
        self.total_amount = self.subtotal + self.tax_amount
        self.save()


class RecurringInvoice(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='recurring_invoices')
    client = models.ForeignKey('business.Client', on_delete=models.CASCADE, related_name='recurring_invoices')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    interval = models.PositiveIntegerField(default=1)

    start_date = models.DateField()
    next_run_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    active = models.BooleanField(default=True)

    # Template for invoice creation. Example keys: line_items, tax_rate, currency, notes, due_days
    template = models.JSONField(blank=True, null=True)

    last_generated_at = models.DateTimeField(blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_invoices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Recurring {self.id} for {self.client.name} ({self.frequency})"

    def schedule_next_run(self):
        import datetime

        if not self.next_run_date:
            base = self.start_date
        else:
            base = self.next_run_date

        if self.frequency == 'daily':
            return base + datetime.timedelta(days=self.interval)
        if self.frequency == 'weekly':
            return base + datetime.timedelta(weeks=self.interval)
        if self.frequency == 'monthly':
            # naive month add
            month = (base.month - 1) + self.interval
            year = base.year + month // 12
            month = month % 12 + 1
            day = min(base.day, self._last_day_of_month(year, month))
            return base.replace(year=year, month=month, day=day)
        if self.frequency == 'yearly':
            try:
                return base.replace(year=base.year + self.interval)
            except Exception:
                # handle feb 29
                return base + datetime.timedelta(days=365 * self.interval)
        # default: monthly
        return base

    @staticmethod
    def _last_day_of_month(year, month):
        import calendar
        return calendar.monthrange(year, month)[1]


class ReminderRule(models.Model):
    """Defines rules for sending email reminders for invoices.
    Can target a business-wide rule or specific invoice.
    """
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='reminder_rules')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='reminder_rules', blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)

    # Send X days before due date
    days_before_due = models.IntegerField(default=3)
    # Also send on overdue days after due_date when invoice is unpaid
    send_on_overdue = models.BooleanField(default=True)

    # Optional subject and message templates (Django template syntax)
    subject_template = models.CharField(max_length=255, blank=True, null=True)
    text_template = models.TextField(blank=True, null=True)

    active = models.BooleanField(default=True)
    last_sent = models.DateTimeField(blank=True, null=True)

    created_by = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='reminder_rules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ReminderRule {self.id} for {self.business.name}"

    def get_target_invoices(self):
        """Return invoices that match this rule and need a reminder."""
        from django.utils import timezone
        today = timezone.now().date()
        qs = Invoice.objects.filter(business=self.business, created_by=self.created_by)
        if self.invoice:
            qs = qs.filter(pk=self.invoice.pk)

        # invoices with due_date == today + days_before_due
        due_date_target = today + timezone.timedelta(days=self.days_before_due)
        candidates = qs.filter(status='sent')
        targets = candidates.filter(due_date=due_date_target)

        if self.send_on_overdue:
            overdue_candidates = candidates.filter(due_date__lt=today)
            targets = targets | overdue_candidates

        return targets.distinct()


class InvoiceTemplate(models.Model):
    """Stores invoice template defaults and HTML for rendering."""
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='invoice_templates')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    # Structured defaults for creating invoices from template
    defaults = models.JSONField(blank=True, null=True)

    # Optional HTML template used for PDF rendering (can be empty and default template used)
    html_template = models.TextField(blank=True, null=True)

    is_default = models.BooleanField(default=False)

    created_by = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='invoice_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.business.name})"


class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    description = models.TextField()
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.description[:50]}..."


class Receipt(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('check', 'Check'),
        ('online', 'Online Payment'),
        ('other', 'Other'),
    ]

    receipt_number = models.CharField(max_length=50, unique=True)
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='receipt')
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='receipts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Receipt {self.receipt_number} for Invoice {self.invoice.invoice_number}"


@receiver([post_save, post_delete], sender=InvoiceLineItem)
def update_invoice_totals(sender, instance, **kwargs):
    """
    Signal handler to recalculate invoice totals when a line item is saved or deleted.
    """
    if instance.invoice:
        instance.invoice.calculate_totals()
