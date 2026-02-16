from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Avg, Sum
from core.models import DailyReport, TicketEntry, StaffPerformance
from weasyprint import HTML
import datetime

class Command(BaseCommand):
    help = 'Generates and emails the weekly PDF report'

    def handle(self, *args, **kwargs):
        self.stdout.write("Generating Weekly Report...")

        # 1. Calculate Dates (Last 7 Days)
        today = timezone.now().date()
        start_date = today - datetime.timedelta(days=7)
        
        # 2. Query Data
        reports = DailyReport.objects.filter(date__range=[start_date, today])
        tickets = TicketEntry.objects.filter(report__in=reports).select_related('staff')
        
        # 3. Calculate Stats
        total_travel = tickets.aggregate(Sum('travel_time_minutes'))['travel_time_minutes__sum'] or 0
        avg_rating = StaffPerformance.objects.filter(report__in=reports).aggregate(Avg('rating'))['rating__avg'] or 0

        context = {
            'start_date': start_date,
            'end_date': today,
            'total_tickets': tickets.count(),
            'avg_rating': round(avg_rating, 1),
            'total_travel': total_travel,
            'tickets': tickets,
        }

        # 4. Generate PDF
        html_string = render_to_string('reports/weekly_pdf.html', context)
        pdf_file = HTML(string=html_string).write_pdf()

        # 5. Send Email
        subject = f"Weekly IT Ops Report: {start_date} - {today}"
        body = "Attached is the weekly summary of IT operations."
        
        email = EmailMessage(
            subject,
            body,
            'system@bperformance.local', # From
            ['manager@yourcompany.com'], # To (Change this to your real email)
        )
        email.attach(f'Report_{today}.pdf', pdf_file, 'application/pdf')
        email.send()

        self.stdout.write(self.style.SUCCESS(f'Successfully emailed report to manager@yourcompany.com'))