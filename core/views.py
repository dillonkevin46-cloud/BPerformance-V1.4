from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db.models import Count, Avg, Sum
from django.http import HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from datetime import datetime, timedelta
import weasyprint
import json
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# IMPORT MODELS
from .models import (
    DailyReport, TicketEntry, StaffMetric, StaffProfile, Department, 
    Client, Category, TicketAttachment, RatingCriteria, 
    StaffWarning, StaffNote, ScheduleSlot, ScheduleChangeLog,
    CheckFormTemplate, CheckFormSubmission, CheckFormFolder
)

# IMPORT FORMS
from .forms import (
    StaffForm, DepartmentForm, ClientForm, CategoryForm, 
    CriteriaForm, WarningForm, StaffNoteForm, SystemUserForm,
    WeeklyReportForm, ScheduleSlotForm, CheckFormTemplateForm, CheckFormFolderForm
)
from django.conf import settings

@login_required
def export_staff_pdf_view(request, staff_id):
    staff = get_object_or_404(StaffProfile, id=staff_id)
    
    # Get Date Range (Defaults to last 30 days)
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    
    today = timezone.now().date()
    if start_str and end_str:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    else:
        end_date = today
        start_date = today - timedelta(days=30)

    # Fetch Data
    tickets = TicketEntry.objects.filter(staff=staff, report__date__range=[start_date, end_date]).order_by('-report__date')
    
    # Calculate Stats
    total_tickets = tickets.count()
    unique_clients = tickets.values('client').distinct().count()
    avg_resolution = tickets.aggregate(Avg('total_work_minutes'))['total_work_minutes__avg'] or 0
    avg_response = tickets.aggregate(Avg('response_minutes'))['response_minutes__avg'] or 0
    
    # Helper to format minutes
    def fmt_mins(m):
        if not m: return "0m"
        h = int(m // 60)
        mn = int(m % 60)
        return f"{h}h {mn}m" if h > 0 else f"{mn}m"

    # --- FEATURE 3: Matplotlib Graph ---
    # Query Metrics
    criteria_stats = StaffMetric.objects.filter(staff=staff, report__date__range=[start_date, end_date]) \
        .values('criteria__name') \
        .annotate(avg_score=Avg('score'))
    
    labels = [item['criteria__name'] for item in criteria_stats]
    scores = [round(item['avg_score'], 1) for item in criteria_stats]

    graph = None
    if labels:
        plt.figure(figsize=(6, 4))
        plt.bar(labels, scores, color='#3498db')
        plt.xlabel('Criteria')
        plt.ylabel('Average Score (1-10)')
        plt.title('Performance Ratings')
        plt.ylim(0, 10)
        plt.tight_layout()
        
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        plt.close() # Clear memory
        
        graph = base64.b64encode(image_png).decode('utf-8')

    context = {
        'staff': staff,
        'tickets': tickets,
        'start_date': start_date,
        'end_date': end_date,
        'total_tickets': total_tickets,
        'unique_clients': unique_clients,
        'avg_resolution': fmt_mins(avg_resolution),
        'avg_response': fmt_mins(avg_response),
        'host': request.build_absolute_uri('/')[:-1], # For images
        'graph': graph # Pass base64 string
    }

    # Generate PDF
    html_string = render_to_string('staff/pdf_stats.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Staff_Report_{staff.full_name}_{end_date}.pdf"'
    weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response

# --- 1. DASHBOARD ---
@login_required
def dashboard_view(request):
    period = request.GET.get('period', 'monthly')
    
    # Custom Range Logic
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    
    today = timezone.now().date()
    start_date = None
    end_date = None

    if start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            period_label = f"{start_date} to {end_date}"
            period = 'custom'
        except ValueError:
            start_date = None # Fallback

    if not start_date:
        # 1. Date Logic
        end_date = today
        if period == 'daily':
            start_date = today
            period_label = "Today's Performance"
        elif period == 'weekly':
            start_date = today - timedelta(days=7)
            period_label = "Last 7 Days"
        elif period == 'yearly':
            start_date = today - timedelta(days=365)
            period_label = "Last 365 Days"
        else:
            start_date = today - timedelta(days=30)
            period_label = "Last 30 Days"

    base_tickets = TicketEntry.objects.filter(report__date__range=[start_date, end_date])

    # 2. Stats Helper
    def get_stats(queryset):
        total = queryset.count()
        if total == 0: return None
        
        work_mins = queryset.aggregate(Sum('total_work_minutes'))['total_work_minutes__sum'] or 0
        travel_mins = queryset.aggregate(Sum('travel_minutes'))['travel_minutes__sum'] or 0
        
        # Status Colors
        status_data = list(queryset.values('status').annotate(count=Count('id')))
        status_map = {
            'COMP': '#2ecc71', 'BLOCK': '#e74c3c', 'PEND': '#f1c40f',
            'HOLD': '#95a5a6', 'CALL': '#e67e22', 'WAIT_ST': '#3498db', 'WAIT_CL': '#9b59b6'
        }
        
        # Top 5 Categories
        cat_data = list(queryset.values('category__name', 'category__color').annotate(count=Count('id')).order_by('-count')[:5])
        
        # Top 5 Clients
        client_data = list(queryset.values('client__name', 'client__color').annotate(count=Count('id')).order_by('-count')[:5])
        
        # Staff Counts
        staff_data = list(queryset.values('staff__full_name').annotate(count=Count('id')).order_by('-count')[:5])

        # --- NEW: Staff Response Time (Avg Mins) ---
        # Calculates average wait time (Requested -> Start) per staff member
        staff_resp = list(queryset.filter(response_minutes__gte=0).values('staff__full_name').annotate(avg_wait=Avg('response_minutes')).order_by('avg_wait'))

        return {
            'total': total,
            'hours': round(work_mins / 60, 2),
            'travel_hours': round(travel_mins / 60, 2),
            
            # Chart Arrays
            'status_labels': [item['status'] for item in status_data],
            'status_counts': [item['count'] for item in status_data],
            'status_colors': [status_map.get(item['status'], '#7f8c8d') for item in status_data],
            
            'cat_labels': [item['category__name'] for item in cat_data],
            'cat_counts': [item['count'] for item in cat_data],
            'cat_colors': [item['category__color'] for item in cat_data], 
            
            'client_labels': [item['client__name'] for item in client_data],
            'client_counts': [item['count'] for item in client_data],
            'client_colors': [item['client__color'] for item in client_data],
            
            'staff_labels': [item['staff__full_name'] for item in staff_data],
            'staff_counts': [item['count'] for item in staff_data],
            
            # Response Time Data
            'resp_labels': [item['staff__full_name'] for item in staff_resp],
            'resp_data': [int(item['avg_wait']) for item in staff_resp],
        }

    # 3. Aggregations
    overview_stats = get_stats(base_tickets)
    
    # Extra Work Type Pie Chart Data for Overview
    type_data = list(base_tickets.values('work_type').annotate(count=Count('id')))
    if overview_stats:
        overview_stats['type_labels'] = [item['work_type'] for item in type_data]
        overview_stats['type_counts'] = [item['count'] for item in type_data]

    # Calculate stats for specific tabs
    ext_stats = get_stats(base_tickets.filter(work_type='EXT'))
    int_stats = get_stats(base_tickets.filter(work_type='INT'))
    rem_stats = get_stats(base_tickets.filter(work_type='REM'))
    adm_stats = get_stats(base_tickets.filter(work_type='ADM'))

    manager_logs = DailyReport.objects.filter(
        date__range=[start_date, end_date]
    ).exclude(manager_notes='').exclude(manager_notes__isnull=True).order_by('-date')

    context = {
        'overview': overview_stats,
        'ext': ext_stats, 'int': int_stats, 'rem': rem_stats, 'adm': adm_stats,
        'manager_logs': manager_logs, 'period': period, 'period_label': period_label,
        'start_date': start_date, 'end_date': end_date
    }
    return render(request, 'dashboard.html', context)

# ... (Keep all other views: staff_index, daily_report, archive, settings, htmx etc. exactly the same) ...
# --- 2. STAFF PROFILES ---
@login_required
def staff_index_view(request):
    staff_members = StaffProfile.objects.filter(is_active=True)
    return render(request, 'staff/index.html', {'staff_members': staff_members})

@login_required
def staff_detail_view(request, staff_id):
    staff = get_object_or_404(StaffProfile, id=staff_id)
    warning_form = WarningForm()
    note_form = StaffNoteForm()

    if request.method == 'POST':
        if 'add_warning' in request.POST:
            warning_form = WarningForm(request.POST, request.FILES)
            if warning_form.is_valid():
                warning = warning_form.save(commit=False)
                warning.staff = staff
                warning.save()
                return redirect('staff_detail', staff_id=staff.id)
        elif 'add_note' in request.POST:
            note_form = StaffNoteForm(request.POST)
            if note_form.is_valid():
                note = note_form.save(commit=False)
                note.staff = staff
                note.created_by = request.user
                note.save()
                return redirect('staff_detail', staff_id=staff.id)

    # --- STATISTICS (Last 30 Days) ---
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    tickets = TicketEntry.objects.filter(staff=staff, report__date__range=[start_date, end_date])
    
    total_tickets = tickets.count()
    unique_clients = tickets.values('client').distinct().count()
    
    status_data = list(tickets.values('status').annotate(count=Count('id')))
    status_labels = [item['status'] for item in status_data]
    status_counts = [item['count'] for item in status_data]
    
    avg_resolution = tickets.aggregate(Avg('total_work_minutes'))['total_work_minutes__avg'] or 0
    avg_response = tickets.aggregate(Avg('response_minutes'))['response_minutes__avg'] or 0

    def fmt_mins(m):
        if not m: return "0m"
        h = int(m // 60)
        mn = int(m % 60)
        return f"{h}h {mn}m" if h > 0 else f"{mn}m"

    criteria_stats = StaffMetric.objects.filter(staff=staff, report__date__range=[start_date, end_date]) \
        .values('criteria__name') \
        .annotate(avg_score=Avg('score'))
    chart_labels = [item['criteria__name'] for item in criteria_stats]
    chart_data = [round(item['avg_score'], 1) for item in criteria_stats]

    # --- ALL TICKETS ---
    all_tickets = TicketEntry.objects.filter(staff=staff).order_by('-report__date', '-start_time')

    return render(request, 'staff/detail.html', {
        'staff': staff,
        'warnings': staff.warnings.all().order_by('-date'),
        'notes': staff.notes.all().order_by('-date'),
        'total_tickets': total_tickets,
        'unique_clients': unique_clients,
        'avg_resolution': fmt_mins(avg_resolution),
        'avg_response': fmt_mins(avg_response),
        'status_labels': status_labels,
        'status_counts': status_counts,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'warning_form': warning_form,
        'note_form': note_form,
        'all_tickets': all_tickets,
    })

# --- 3. DAILY REPORT EDITOR ---
@login_required
def daily_report_view(request, date_str=None):
    if date_str:
        try: target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError: target_date = timezone.now().date()
    else: target_date = timezone.now().date()

    report, created = DailyReport.objects.get_or_create(date=target_date, defaults={'created_by': request.user})
    
    todays_tickets = report.entries.select_related('staff', 'client', 'category').prefetch_related('attachments').all().order_by('-start_time')
    
    # --- FILTERS ---
    filter_staff = request.GET.get('staff')
    filter_client = request.GET.get('client')
    filter_status = request.GET.get('status')
    
    if filter_staff and filter_staff.isdigit(): 
        todays_tickets = todays_tickets.filter(staff_id=filter_staff)
    if filter_client and filter_client.isdigit(): 
        todays_tickets = todays_tickets.filter(client_id=filter_client)
    if filter_status: 
        todays_tickets = todays_tickets.filter(status=filter_status)

    active_staff = StaffProfile.objects.filter(is_active=True)
    active_criteria = RatingCriteria.objects.filter(is_active=True)
    
    # Initialize Metrics
    for staff in active_staff:
        for crit in active_criteria:
            StaffMetric.objects.get_or_create(report=report, staff=staff, criteria=crit, defaults={'score': 5})
    
    staff_metrics_map = {}
    metrics = StaffMetric.objects.filter(report=report).select_related('staff', 'criteria').order_by('staff', 'criteria')
    for m in metrics:
        if m.staff not in staff_metrics_map: staff_metrics_map[m.staff] = []
        staff_metrics_map[m.staff].append(m)

    return render(request, 'daily_report.html', {
        'report': report,
        'tickets': todays_tickets,
        'staff_metrics_map': staff_metrics_map,
        'staff_list': active_staff,
        'client_list': Client.objects.filter(is_active=True),
        'category_list': Category.objects.filter(is_active=True),
        'current_date': target_date,
        'filter_staff': int(filter_staff) if filter_staff and filter_staff.isdigit() else None,
        'filter_client': int(filter_client) if filter_client and filter_client.isdigit() else None,
        'filter_status': filter_status,
        'status_choices': TicketEntry.STATUS_CHOICES,
    })

# --- 4. ARCHIVE & EMAIL ---
@login_required
def report_archive_view(request):
    reports = DailyReport.objects.all().order_by('-date')
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        reports = reports.filter(date__range=[start_date, end_date])
        
    return render(request, 'reports/archive.html', {'reports': reports})

@login_required
def send_weekly_report_view(request):
    if request.method == 'POST':
        form = WeeklyReportForm(request.POST)
        if form.is_valid():
            start = form.cleaned_data['start_date']
            end = form.cleaned_data['end_date']
            recipients = [e.strip() for e in form.cleaned_data['recipients'].split(',')]

            reports = DailyReport.objects.filter(date__range=[start, end]).order_by('date')
            
            context = {
                'reports': reports, 
                'start_date': start, 
                'end_date': end,
                'host': request.build_absolute_uri('/')[:-1]
            }
            html_string = render_to_string('reports/weekly_pdf_template.html', context)
            pdf_file = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

            subject = f"Weekly Operations Report: {start} to {end}"
            body = f"Please find attached the combined operations report for the period {start} to {end}.\n\nGenerated by BPerformance."
            
            email = EmailMessage(subject, body, 'noreply@bperformance.com', recipients)
            email.attach(f'Weekly_Report_{start}_{end}.pdf', pdf_file, 'application/pdf')
            email.send()
            
            return redirect('report_archive')
    return redirect('report_archive')

@login_required
def mark_report_submitted(request, report_id):
    report = get_object_or_404(DailyReport, id=report_id)
    report.is_submitted = True
    report.save()
    return redirect('daily_report_date', date_str=report.date)

@login_required
def generate_pdf_view(request, report_id):
    report = get_object_or_404(DailyReport, id=report_id)
    tickets = report.entries.select_related('staff', 'client', 'category').all().order_by('start_time')
    
    staff_metrics_map = {}
    metrics = StaffMetric.objects.filter(report=report).select_related('staff', 'criteria').order_by('staff')
    for m in metrics:
        if m.staff not in staff_metrics_map: staff_metrics_map[m.staff] = []
        staff_metrics_map[m.staff].append(m)

    context = {
        'report': report,
        'tickets': tickets,
        'staff_metrics_map': staff_metrics_map,
        'host': request.build_absolute_uri('/')[:-1]
    }
    
    html_string = render_to_string('reports/pdf_template.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Report_{report.date}.pdf"'
    weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response

# --- 5. SETTINGS ---
@login_required
def manage_settings_view(request):
    staff_list = StaffProfile.objects.all()
    departments = Department.objects.all()
    clients = Client.objects.all()
    categories = Category.objects.all()
    criteria_list = RatingCriteria.objects.all()
    system_users = User.objects.filter(is_superuser=False)

    staff_form = StaffForm()
    dept_form = DepartmentForm()
    client_form = ClientForm()
    cat_form = CategoryForm()
    crit_form = CriteriaForm()
    user_form = SystemUserForm()

    if request.method == 'POST':
        if 'add_staff' in request.POST:
            staff_form = StaffForm(request.POST, request.FILES)
            if staff_form.is_valid(): staff_form.save(); return redirect('settings')
        elif 'add_dept' in request.POST:
            dept_form = DepartmentForm(request.POST)
            if dept_form.is_valid(): dept_form.save(); return redirect('settings')
        elif 'add_client' in request.POST:
            client_form = ClientForm(request.POST)
            if client_form.is_valid(): client_form.save(); return redirect('settings')
        elif 'add_cat' in request.POST:
            cat_form = CategoryForm(request.POST)
            if cat_form.is_valid(): cat_form.save(); return redirect('settings')
        elif 'add_crit' in request.POST:
            crit_form = CriteriaForm(request.POST)
            if crit_form.is_valid(): crit_form.save(); return redirect('settings')
        elif 'add_user' in request.POST:
            user_form = SystemUserForm(request.POST)
            if user_form.is_valid(): user_form.save(); return redirect('settings')

    return render(request, 'settings.html', {
        'staff_list': staff_list, 'departments': departments, 'clients': clients, 
        'categories': categories, 'criteria_list': criteria_list, 'system_users': system_users,
        'staff_form': staff_form, 'dept_form': dept_form, 'client_form': client_form, 
        'cat_form': cat_form, 'crit_form': crit_form, 'user_form': user_form
    })

# --- 6. HTMX & UTILS ---
def calc_mins(start_str, end_str):
    if not start_str or not end_str: return 0
    fmt = '%H:%M'
    try:
        t1 = datetime.strptime(str(start_str)[:5], fmt)
        t2 = datetime.strptime(str(end_str)[:5], fmt)
        diff = t2 - t1
        return int(diff.total_seconds() / 60)
    except ValueError: return 0

@login_required
@require_POST
def htmx_add_ticket(request, report_id):
    report = get_object_or_404(DailyReport, id=report_id)
    work_mins = calc_mins(request.POST.get('start_time'), request.POST.get('end_time'))
    travel_mins = calc_mins(request.POST.get('travel_start'), request.POST.get('travel_end'))
    
    # Calc Response Minutes
    req_str = request.POST.get('requested_time')
    start_str = request.POST.get('start_time')
    response_mins = 0
    if req_str and start_str:
        try:
            t_req = datetime.strptime(str(req_str)[:5], '%H:%M')
            t_start = datetime.strptime(str(start_str)[:5], '%H:%M')
            diff = t_start - t_req
            response_mins = int(diff.total_seconds() / 60)
        except ValueError: pass

    ticket = TicketEntry.objects.create(
        report=report,
        staff_id=request.POST.get('staff'),
        client_id=request.POST.get('client'),
        category_id=request.POST.get('category'),
        work_type=request.POST.get('work_type'),
        status=request.POST.get('status'),
        work_location=request.POST.get('work_location'),
        description=request.POST.get('description'),
        manager_ticket_notes=request.POST.get('manager_ticket_notes') or "",
        
        requested_time=request.POST.get('requested_time'),
        start_time=request.POST.get('start_time'),
        end_time=request.POST.get('end_time'),
        travel_start_time=request.POST.get('travel_start') or None,
        travel_end_time=request.POST.get('travel_end') or None,
        
        total_work_minutes=work_mins,
        travel_minutes=travel_mins,
        response_minutes=response_mins
    )

    files = request.FILES.getlist('attachments')
    for f in files: TicketAttachment.objects.create(ticket=ticket, file=f)
    
    tickets = report.entries.select_related('staff', 'client', 'category').prefetch_related('attachments').all().order_by('-start_time')
    return render(request, 'partials/ticket_list.html', {'tickets': tickets})

@login_required
@require_http_methods(["GET"])
def htmx_get_edit_form(request, ticket_id):
    ticket = get_object_or_404(TicketEntry, id=ticket_id)
    context = {
        'ticket': ticket,
        'staff_list': StaffProfile.objects.filter(is_active=True),
        'client_list': Client.objects.filter(is_active=True),
        'category_list': Category.objects.filter(is_active=True),
    }
    return render(request, 'partials/ticket_edit_row.html', context)

@login_required
@require_POST
def htmx_save_ticket(request, ticket_id):
    ticket = get_object_or_404(TicketEntry, id=ticket_id)
    ticket.staff_id = request.POST.get('staff')
    ticket.client_id = request.POST.get('client')
    ticket.category_id = request.POST.get('category')
    ticket.work_type = request.POST.get('work_type')
    ticket.status = request.POST.get('status')
    ticket.work_location = request.POST.get('work_location')
    ticket.description = request.POST.get('description')
    ticket.manager_ticket_notes = request.POST.get('manager_ticket_notes') or ""
    
    ticket.requested_time = request.POST.get('requested_time')
    ticket.start_time = request.POST.get('start_time')
    ticket.end_time = request.POST.get('end_time')
    ticket.travel_start_time = request.POST.get('travel_start') or None
    ticket.travel_end_time = request.POST.get('travel_end') or None
    
    ticket.total_work_minutes = calc_mins(ticket.start_time, ticket.end_time)
    ticket.travel_minutes = calc_mins(request.POST.get('travel_start'), request.POST.get('travel_end'))
    
    # Calc Response Minutes
    response_mins = 0
    if ticket.requested_time and ticket.start_time:
        try:
            t_req = datetime.strptime(str(ticket.requested_time)[:5], '%H:%M')
            t_start = datetime.strptime(str(ticket.start_time)[:5], '%H:%M')
            diff = t_start - t_req
            response_mins = int(diff.total_seconds() / 60)
        except ValueError: pass
    ticket.response_minutes = response_mins
    
    ticket.save()

    files = request.FILES.getlist('attachments')
    for f in files: TicketAttachment.objects.create(ticket=ticket, file=f)
    
    ticket = TicketEntry.objects.select_related('staff', 'client', 'category').prefetch_related('attachments').get(id=ticket.id)
    return render(request, 'partials/ticket_row.html', {'ticket': ticket})

@login_required
@require_POST
def htmx_delete_ticket(request, ticket_id):
    ticket = get_object_or_404(TicketEntry, id=ticket_id)
    ticket.delete()
    return HttpResponse("") 

@login_required
@require_POST
def htmx_update_metric_score(request, metric_id):
    metric = get_object_or_404(StaffMetric, id=metric_id)
    metric.score = request.POST.get('score')
    metric.save()
    return HttpResponse("")

@login_required
@require_POST
def htmx_save_metric_note(request, metric_id):
    metric = get_object_or_404(StaffMetric, id=metric_id)
    metric.notes = request.POST.get('notes') or ""
    metric.save()
    return HttpResponse("")

@login_required
@require_POST
def htmx_save_notes(request, report_id):
    report = get_object_or_404(DailyReport, id=report_id)
    report.manager_notes = request.POST.get('manager_notes')
    report.save()
    return HttpResponse('<span class="text-success small">Saved!</span>')

@login_required
def htmx_staff_tickets(request, staff_id):
    staff = get_object_or_404(StaffProfile, id=staff_id)
    
    query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort', 'newest') # newest, oldest
    
    tickets = TicketEntry.objects.filter(staff=staff).select_related('staff', 'client', 'category')
    
    # 1. Search
    if query:
        # Search by ID or Description
        if query.isdigit():
            tickets = tickets.filter(id=query)
        else:
            tickets = tickets.filter(description__icontains=query)
            
    # 2. Filter
    if status_filter:
        tickets = tickets.filter(status=status_filter)
        
    # 3. Sort
    if sort_by == 'oldest':
        tickets = tickets.order_by('report__date', 'start_time')
    else: # newest
        tickets = tickets.order_by('-report__date', '-start_time')
        
    return render(request, 'partials/staff_ticket_list.html', {'tickets': tickets})

# --- 7. DELETION ACTIONS ---
@login_required
def delete_setting_item(request, model_type, item_id):
    if model_type == 'client':
        Client.objects.filter(id=item_id).delete()
    elif model_type == 'category':
        Category.objects.filter(id=item_id).delete()
    elif model_type == 'criteria':
        RatingCriteria.objects.filter(id=item_id).delete()
    elif model_type == 'staff':
        StaffProfile.objects.filter(id=item_id).delete()
    elif model_type == 'dept':
        Department.objects.filter(id=item_id).delete()
    return redirect('settings')

@login_required
def delete_staff_note(request, note_id):
    note = get_object_or_404(StaffNote, id=note_id)
    staff_id = note.staff.id
    note.delete()
    return redirect('staff_detail', staff_id=staff_id)

@login_required
def delete_staff_warning(request, warning_id):
    warning = get_object_or_404(StaffWarning, id=warning_id)
    staff_id = warning.staff.id
    warning.delete()
    return redirect('staff_detail', staff_id=staff_id)

# --- 8. SCHEDULER ---

@login_required
def scheduler_dashboard_view(request):
    date_str = request.GET.get('date')
    if date_str:
        try: target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError: target_date = timezone.now().date()
    else: target_date = timezone.now().date()
    
    # Get slots for this day
    # Start of day, End of day
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())
    
    slots = ScheduleSlot.objects.filter(start_time__range=(start_of_day, end_of_day)).select_related('staff')
    staff_members = StaffProfile.objects.filter(is_active=True)
    
    # Calculate changes today
    changes_count = ScheduleChangeLog.objects.filter(timestamp__date=timezone.now().date()).count()

    return render(request, 'scheduler/dashboard.html', {
        'current_date': target_date,
        'slots': slots,
        'staff_members': staff_members,
        'changes_count': changes_count
    })

@login_required
@require_POST
def htmx_add_schedule_slot(request):
    # Form handling
    staff_id = request.POST.get('staff')
    location = request.POST.get('location')
    start_time = request.POST.get('start_time') # Format: YYYY-MM-DDTHH:MM
    end_time = request.POST.get('end_time')
    description = request.POST.get('description')
    
    staff = get_object_or_404(StaffProfile, id=staff_id)
    
    slot = ScheduleSlot.objects.create(
        staff=staff,
        location=location,
        start_time=start_time,
        end_time=end_time,
        description=description,
        status='PENDING'
    )
    
    log = ScheduleChangeLog.objects.create(
        slot=slot,
        action_type='CREATE',
        requested_by=request.user,
    )
    
    send_approval_email(request, log)
    
    return redirect('scheduler_dashboard')

@login_required
@require_POST
def htmx_delete_schedule_slot(request, slot_id):
    slot = get_object_or_404(ScheduleSlot, id=slot_id)
    slot.status = 'PENDING_DELETE'
    slot.save()
    
    log = ScheduleChangeLog.objects.create(
        slot=slot,
        action_type='DELETE',
        requested_by=request.user,
    )
    
    send_approval_email(request, log)
    
    return redirect('scheduler_dashboard')

@login_required
@require_POST
def htmx_move_schedule_slot(request, slot_id):
    slot = get_object_or_404(ScheduleSlot, id=slot_id)
    
    new_start = request.POST.get('start_time')
    new_end = request.POST.get('end_time')
    
    # Store previous
    prev_start = slot.start_time
    prev_end = slot.end_time
    
    slot.start_time = new_start
    slot.end_time = new_end
    slot.status = 'PENDING'
    slot.save()
    
    log = ScheduleChangeLog.objects.create(
        slot=slot,
        action_type='UPDATE',
        requested_by=request.user,
        previous_start=prev_start,
        previous_end=prev_end
    )
    
    send_approval_email(request, log)
    
    return redirect('scheduler_dashboard')

@login_required
def scheduler_history_view(request):
    logs = ScheduleChangeLog.objects.all().order_by('-timestamp').select_related('slot', 'requested_by', 'approved_by')
    return render(request, 'scheduler/history.html', {'logs': logs})

@login_required 
def scheduler_approval_landing(request, log_id, action):
    log = get_object_or_404(ScheduleChangeLog, id=log_id)
    return render(request, 'scheduler/approval_landing.html', {'log': log, 'action': action})

@login_required
@require_POST
def scheduler_finalize_approval(request, log_id):
    log = get_object_or_404(ScheduleChangeLog, id=log_id)
    action = request.POST.get('action') # approve, reject
    comments = request.POST.get('comments')
    
    log.comments = comments
    log.approved_by = request.user
    log.save()
    
    slot = log.slot
    
    if action == 'approve':
        if log.action_type == 'DELETE':
            slot.delete()
        else:
            slot.status = 'APPROVED'
            slot.save()
    elif action == 'reject':
        if log.action_type == 'CREATE':
            slot.status = 'REJECTED' 
            slot.save()
        elif log.action_type == 'UPDATE':
            # Revert
            if log.previous_start and log.previous_end:
                slot.start_time = log.previous_start
                slot.end_time = log.previous_end
                slot.status = 'APPROVED' 
                slot.save()
        elif log.action_type == 'DELETE':
            slot.status = 'APPROVED'
            slot.save()
    
    return redirect('scheduler_history')

def send_approval_email(request, log):
    approver_email = getattr(settings, 'APPROVER_EMAIL', 'admin@example.com')
    
    context = {
        'log': log,
        'slot': log.slot,
        'host': request.build_absolute_uri('/')[:-1]
    }
    html_content = render_to_string('scheduler/email_approval.html', context)
    
    email = EmailMessage(
        subject=f"Schedule Approval Required: {log.get_action_type_display()}",
        body=html_content,
        to=[approver_email]
    )
    email.content_subtype = "html"
    email.send()

@login_required
def scheduler_generate_pdf_view(request, date_str):
    try: target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError: target_date = timezone.now().date()
    
    # Feature 1: Get logs for this day
    logs = ScheduleChangeLog.objects.filter(timestamp__date=target_date).order_by('timestamp')
    
    html_string = f"""
    <html>
    <head><style>
        body {{ font-family: sans-serif; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style></head>
    <body>
        <h1>Scheduler Change Log</h1>
        <h3>Date: {target_date}</h3>
        <table>
            <tr>
                <th>Time</th>
                <th>Action</th>
                <th>Staff Modified</th>
                <th>Approved By</th>
                <th>Details (Old -> New)</th>
            </tr>
    """
    
    for log in logs:
        details = ""
        if log.action_type == 'UPDATE' and log.previous_start:
             details = f"Time: {log.previous_start.strftime('%H:%M')} -> {log.slot.start_time.strftime('%H:%M')}"
        elif log.action_type == 'CREATE':
             details = f"Created: {log.slot.start_time.strftime('%H:%M')} - {log.slot.end_time.strftime('%H:%M')}"
        elif log.action_type == 'DELETE':
             details = "Slot Deleted"
             
        approver = log.approved_by.username if log.approved_by else "Pending"
        
        html_string += f"""
            <tr>
                <td>{log.timestamp.strftime('%H:%M')}</td>
                <td>{log.get_action_type_display()}</td>
                <td>{log.slot.staff.full_name}</td>
                <td>{approver}</td>
                <td>{details}</td>
            </tr>
        """
        
    html_string += """
        </table>
    </body>
    </html>
    """
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Schedule_Log_{target_date}.pdf"'
    weasyprint.HTML(string=html_string).write_pdf(response)
    return response


# --- 9. CHECK FORMS ---

@login_required
def checkform_admin_view(request):
    folders = CheckFormFolder.objects.all()
    inbox = CheckFormSubmission.objects.filter(status='COMPLETED', folder__isnull=True).order_by('-submitted_at')
    
    # Filing Logic
    if request.method == 'POST' and 'file_submission' in request.POST:
        sub_id = request.POST.get('submission_id')
        folder_id = request.POST.get('folder_id')
        sub = get_object_or_404(CheckFormSubmission, id=sub_id)
        folder = get_object_or_404(CheckFormFolder, id=folder_id)
        sub.folder = folder
        sub.status = 'FILED'
        sub.save()
        return redirect('checkform_admin')
    
    # Create Folder Logic
    folder_form = CheckFormFolderForm()
    if request.method == 'POST' and 'create_folder' in request.POST:
        folder_form = CheckFormFolderForm(request.POST)
        if folder_form.is_valid():
            folder_form.save()
            return redirect('checkform_admin')

    # Selected Folder View
    selected_folder_id = request.GET.get('folder')
    selected_folder_submissions = []
    if selected_folder_id:
        selected_folder_submissions = CheckFormSubmission.objects.filter(folder_id=selected_folder_id).order_by('-submitted_at')

    return render(request, 'checkforms/admin_list.html', {
        'folders': folders,
        'inbox': inbox,
        'folder_form': folder_form,
        'selected_folder_id': int(selected_folder_id) if selected_folder_id else None,
        'selected_folder_submissions': selected_folder_submissions
    })

@login_required
def checkform_builder_view(request):
    templates = CheckFormTemplate.objects.all()
    form = CheckFormTemplateForm()
    
    if request.method == 'POST':
        form = CheckFormTemplateForm(request.POST, request.FILES) # Added FILES for logo
        if form.is_valid():
            template = form.save(commit=False)
            template.created_by = request.user
            # Items
            items_json = request.POST.get('items_json') 
            try:
                template.items = json.loads(items_json)
            except:
                template.items = []
            template.save()
            return redirect('checkform_builder')
            
    return render(request, 'checkforms/builder.html', {'templates': templates, 'form': form})

@login_required
def checkform_share_view(request):
    if request.method == 'POST':
        template_id = request.POST.get('template')
        recipient = request.POST.get('recipient')
        
        template = get_object_or_404(CheckFormTemplate, id=template_id)
        
        submission = CheckFormSubmission.objects.create(
            template=template,
            recipient_email=recipient,
            status='SENT'
        )
        
        # Email Logic
        link = request.build_absolute_uri('/')[:-1] + f"/checkforms/view/{submission.token}/"
        
        subject = f"Checklist Request: {template.title}"
        body = render_to_string('checkforms/email_share.html', {'link': link, 'template': template})
        
        email = EmailMessage(subject, body, 'noreply@bperformance.com', [recipient])
        email.content_subtype = "html"
        email.send()
        
        return redirect('checkform_admin')
        
    templates = CheckFormTemplate.objects.all()
    return render(request, 'checkforms/share.html', {'templates': templates})

# No Login Required
def checkform_external_view(request, token):
    submission = get_object_or_404(CheckFormSubmission, token=token)
    
    if submission.status in ['COMPLETED', 'FILED']:
        return HttpResponse("This form has already been submitted.")
        
    return render(request, 'checkforms/external_form.html', {'submission': submission})

# No Login Required
@require_POST
def checkform_submit_view(request, token):
    submission = get_object_or_404(CheckFormSubmission, token=token)
    
    if submission.status in ['COMPLETED', 'FILED']:
        return HttpResponse("Already submitted.")
        
    # Process Form (Updated for Type A and B)
    items = submission.template.items
    answers = []
    
    # 1. Simple Loop through posted data based on item index
    # We need to handle Type A (check + note) and Type B (table input)
    
    for idx, item in enumerate(items):
        item_type = item.get('type', 'simple') # default legacy
        
        if item_type == 'check_note':
            is_checked = request.POST.get(f"check_{idx}") == 'on'
            note = request.POST.get(f"note_{idx}")
            answers.append({
                'label': item['label'],
                'type': 'check_note',
                'checked': is_checked,
                'note': note
            })
            
        elif item_type == 'fixed_table':
            # Rows are fixed, user inputs last column?
            # Or table structure?
            # Let's assume the template has "rows" and we want to capture an input for each row
            table_rows = item.get('rows', [])
            row_answers = []
            for r_idx, row in enumerate(table_rows):
                val = request.POST.get(f"table_{idx}_row_{r_idx}")
                row_answers.append(val)
            
            answers.append({
                'label': item['label'],
                'type': 'fixed_table',
                'row_inputs': row_answers
            })
            
        else: # Legacy Simple Check
            is_checked = request.POST.get(f"check_{idx}") == 'on'
            comment = request.POST.get(f"comment_{idx}")
            answers.append({
                'label': item['label'],
                'type': 'simple',
                'checked': is_checked,
                'comment': comment
            })
        
    general_comment = request.POST.get('general_comment')
    name = request.POST.get('submitted_by_name')
    
    submission.content = {'answers': answers, 'general_comment': general_comment}
    submission.submitted_by_name = name
    submission.submitted_at = timezone.now()
    submission.status = 'COMPLETED'
    submission.save()
    
    return HttpResponse("<div class='container mt-5'><h1>Thank You!</h1><p>Your submission has been received.</p></div>")
