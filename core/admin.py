from django.contrib import admin
from .models import (
    Department, StaffProfile, DailyReport, TicketEntry, 
    Client, Category, RatingCriteria, StaffMetric, TicketAttachment
)

class StaffInline(admin.TabularInline):
    model = StaffProfile
    extra = 0

class TicketAttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 0

class TicketInline(admin.TabularInline):
    model = TicketEntry
    extra = 0
    fields = ('start_time', 'end_time', 'staff', 'client', 'category', 'work_type', 'status')
    inlines = [TicketAttachmentInline] # This allows seeing attachments inside a ticket

class MetricInline(admin.TabularInline):
    model = StaffMetric
    extra = 0
    readonly_fields = ('staff', 'criteria') # Prevent changing structure here
    can_delete = False

# --- Admin Registrations ---

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name',)
    inlines = [StaffInline]

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'is_active')
    list_filter = ('is_active',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')

@admin.register(RatingCriteria)
class CriteriaAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')

@admin.register(StaffProfile)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'department', 'is_active', 'joined_date')
    list_filter = ('department', 'is_active')
    search_fields = ('full_name',)

@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ('date', 'created_by', 'is_submitted', 'created_at')
    list_filter = ('date', 'is_submitted')
    inlines = [TicketInline, MetricInline]

@admin.register(TicketEntry)
class TicketEntryAdmin(admin.ModelAdmin):
    list_display = ('date_display', 'staff', 'client', 'category', 'status', 'total_work_minutes')
    list_filter = ('work_type', 'status', 'staff', 'category')
    inlines = [TicketAttachmentInline]
    
    def date_display(self, obj):
        return obj.report.date
    date_display.short_description = 'Date'