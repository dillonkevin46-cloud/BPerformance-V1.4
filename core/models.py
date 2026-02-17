from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

# --- 1. CONFIGURATION MODELS ---

class Department(models.Model):
    name = models.CharField(max_length=50, unique=True)
    def __str__(self): return self.name

class Client(models.Model):
    name = models.CharField(max_length=100, unique=True)
    contact_person = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    color = models.CharField(max_length=7, default='#3498db') # Custom Chart Color
    def __str__(self): return self.name
    class Meta: ordering = ['name']

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    color = models.CharField(max_length=7, default='#95a5a6') # Custom Chart Color
    def __str__(self): return self.name
    class Meta: ordering = ['name']

class RatingCriteria(models.Model):
    name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name
    class Meta: ordering = ['name']

class StaffProfile(models.Model):
    full_name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='staff')
    profile_picture = models.ImageField(upload_to='staff_photos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    joined_date = models.DateField(auto_now_add=True)
    def __str__(self): return self.full_name
    class Meta: ordering = ['full_name']

# --- 2. DAILY REPORT ---

class DailyReport(models.Model):
    date = models.DateField(unique=True, default=timezone.now)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    manager_notes = models.TextField(blank=True)
    is_submitted = models.BooleanField(default=False)
    
    def __str__(self): return f"Report {self.date}"
    class Meta: ordering = ['-date']

# --- 3. TICKETS ---

class TicketEntry(models.Model):
    WORK_TYPE_CHOICES = [
        ('INT', 'Internal (Office)'),
        ('EXT', 'External (On-Site)'),
        ('REM', 'Remote Support'),
        ('ADM', 'Admin / Workshop'),
    ]
    STATUS_CHOICES = [
        ('COMP', 'Completed'),
        ('BLOCK', 'Blocker'),       # Was 'Stuck'
        ('PEND', 'Pending'),        # New
        ('HOLD', 'On Hold'),        # New
        ('CALL', 'Call Back'),
        ('WAIT_ST', 'Awaiting Staff'),
        ('WAIT_CL', 'Awaiting Client'),
    ]
    LOCATION_CHOICES = [
        ('OFFICE', 'Office'),
        ('HOME', 'Work from Home'),
        ('HYBRID', 'Hybrid / Travel'),
    ]

    report = models.ForeignKey(DailyReport, on_delete=models.CASCADE, related_name='entries')
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='work_entries')
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='tickets')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='tickets')
    
    # Dropdowns
    work_type = models.CharField(max_length=3, choices=WORK_TYPE_CHOICES, default='INT')
    status = models.CharField(max_length=7, choices=STATUS_CHOICES, default='COMP')
    work_location = models.CharField(max_length=10, choices=LOCATION_CHOICES, default='OFFICE')
    
    # Time Tracking
    requested_time = models.TimeField(default=timezone.now) # When client asked for help
    start_time = models.TimeField(default=timezone.now)     # When work started
    end_time = models.TimeField(default=timezone.now)       # When work finished
    travel_start_time = models.TimeField(blank=True, null=True)
    travel_end_time = models.TimeField(blank=True, null=True)
    
    # Details
    description = models.TextField()
    manager_ticket_notes = models.TextField(blank=True)

    # Calculated Fields (Stored for Analytics)
    total_work_minutes = models.PositiveIntegerField(default=0)
    travel_minutes = models.PositiveIntegerField(default=0)
    response_minutes = models.IntegerField(default=0) # Wait time (Start - Requested)

    @property
    def duration_display(self):
        if self.total_work_minutes == 0: return "0m"
        hours = self.total_work_minutes // 60
        minutes = self.total_work_minutes % 60
        if hours > 0: return f"{hours}h {minutes}m"
        return f"{minutes}m"
    
    @property
    def travel_duration_display(self):
        if self.travel_minutes == 0: return "0m"
        hours = self.travel_minutes // 60
        minutes = self.travel_minutes % 60
        if hours > 0: return f"{hours}h {minutes}m"
        return f"{minutes}m"

    @property
    def response_time_display(self):
        if self.response_minutes <= 0: return "Instant"
        hours = self.response_minutes // 60
        minutes = self.response_minutes % 60
        if hours > 0: return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def __str__(self): return f"{self.staff} - {self.client}"

class TicketAttachment(models.Model):
    ticket = models.ForeignKey(TicketEntry, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='ticket_uploads/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    def filename(self): return self.file.name.split('/')[-1]

# --- 4. STAFF METRICS ---

class StaffMetric(models.Model):
    report = models.ForeignKey(DailyReport, on_delete=models.CASCADE, related_name='metrics')
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='daily_metrics')
    criteria = models.ForeignKey(RatingCriteria, on_delete=models.PROTECT)
    
    score = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)])
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('report', 'staff', 'criteria')
        ordering = ['staff', 'criteria']

# --- 5. HR RECORDS ---

class StaffWarning(models.Model):
    SEVERITY_CHOICES = [
        ('VERBAL', 'Verbal Warning'),
        ('WRITTEN', 'Written Warning'),
        ('FINAL', 'Final Warning'),
        ('PIP', 'Performance Improvement Plan'),
    ]
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='warnings')
    date = models.DateField(default=timezone.now)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    reason = models.CharField(max_length=200)
    description = models.TextField()
    attachment = models.FileField(upload_to='hr_warnings/', blank=True, null=True)

    def __str__(self): return f"{self.staff} - {self.severity}"

class StaffNote(models.Model):
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='notes')
    date = models.DateTimeField(auto_now_add=True)
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self): return f"Note for {self.staff} on {self.date.date()}"

# --- 6. SCHEDULER SYSTEM ---

class ScheduleSlot(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PENDING_DELETE', 'Pending Deletion'),
    ]
    
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='schedule_slots')
    location = models.CharField(max_length=100) # Can be "Office", "Home", or Client Name
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    description = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self): return f"{self.staff} @ {self.start_time}"

class ScheduleChangeLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Created Slot'),
        ('UPDATE', 'Updated Slot'), 
        ('DELETE', 'Deleted Slot'),
    ]
    
    slot = models.ForeignKey(ScheduleSlot, on_delete=models.SET_NULL, null=True, related_name='logs') 
    action_type = models.CharField(max_length=10, choices=ACTION_CHOICES)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='schedule_requests')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='schedule_approvals')
    timestamp = models.DateTimeField(auto_now_add=True)
    comments = models.TextField(blank=True)
    
    # Snapshot data in case of deletion or revert needed
    previous_start = models.DateTimeField(null=True, blank=True)
    previous_end = models.DateTimeField(null=True, blank=True)
    
    def __str__(self): return f"{self.action_type} - {self.timestamp}"

# --- 7. CHECK FORM SYSTEM ---

class CheckFormFolder(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name
    class Meta: verbose_name_plural = "Check Form Folders"

class CheckFormTemplate(models.Model):
    title = models.CharField(max_length=100)
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True) # Feature 2: Added Logo
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # JSON Structure for Items:
    # Type A (Check & Note): 
    #   {"type": "check_note", "label": "Is Safe?", "required": true}
    # Type B (Fixed Table): 
    #   {"type": "fixed_table", "label": "Stock", "columns": [{"name": "Item", "type": "text"}, {"name": "Qty", "type": "text"}, {"name": "Count", "type": "input"}], "rows": [["Widget", "10", ""], ...]}
    items = models.JSONField(default=list) 
    
    instructions = models.TextField(blank=True)
    has_general_comment = models.BooleanField(default=True)
    
    def __str__(self): return self.title

class CheckFormSubmission(models.Model):
    STATUS_CHOICES = [
        ('SENT', 'Sent / Pending'),
        ('COMPLETED', 'Completed'),
        ('FILED', 'Filed'),
    ]
    
    template = models.ForeignKey(CheckFormTemplate, on_delete=models.PROTECT, related_name='submissions')
    recipient_email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SENT')
    
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by_name = models.CharField(max_length=100, blank=True)
    
    content = models.JSONField(null=True, blank=True) # The actual answers
    folder = models.ForeignKey(CheckFormFolder, on_delete=models.SET_NULL, null=True, blank=True, related_name='filed_forms')
    
    def __str__(self): return f"{self.template} - {self.recipient_email}"
