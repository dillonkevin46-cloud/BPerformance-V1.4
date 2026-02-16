from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views

from core.views import (
    dashboard_view, daily_report_view, manage_settings_view,
    htmx_add_ticket, htmx_save_notes, htmx_get_edit_form, htmx_save_ticket,
    htmx_update_metric_score, htmx_save_metric_note, htmx_delete_ticket,
    htmx_staff_tickets,
    report_archive_view, mark_report_submitted, generate_pdf_view,
    staff_index_view, staff_detail_view,
    delete_setting_item, delete_staff_note, delete_staff_warning, send_weekly_report_view,
    # SCHEDULER
    scheduler_dashboard_view, htmx_add_schedule_slot, htmx_move_schedule_slot, htmx_delete_schedule_slot,
    scheduler_approval_landing, scheduler_finalize_approval, scheduler_history_view,
    # CHECK FORMS
    checkform_admin_view, checkform_builder_view, checkform_share_view,
    checkform_external_view, checkform_submit_view
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # AUTHENTICATION
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # APP VIEWS
    path('', dashboard_view, name='dashboard'),
    path('report/', daily_report_view, name='daily_report'),
    path('report/<str:date_str>/', daily_report_view, name='daily_report_date'),
    path('settings/', manage_settings_view, name='settings'),
    path('archive/', report_archive_view, name='report_archive'),
    path('report/submit/<int:report_id>/', mark_report_submitted, name='mark_submitted'),
    path('report/pdf/<int:report_id>/', generate_pdf_view, name='generate_pdf'),
    
    path('staff/', staff_index_view, name='staff_index'),
    path('staff/<int:staff_id>/', staff_detail_view, name='staff_detail'),
    path('report/send-weekly/', send_weekly_report_view, name='send_weekly_report'),

    # HTMX ACTIONS
    path('htmx/add-ticket/<int:report_id>/', htmx_add_ticket, name='htmx_add_ticket'),
    path('htmx/edit-ticket/<int:ticket_id>/', htmx_get_edit_form, name='htmx_get_edit_form'),
    path('htmx/save-ticket/<int:ticket_id>/', htmx_save_ticket, name='htmx_save_ticket'),
    path('htmx/delete-ticket/<int:ticket_id>/', htmx_delete_ticket, name='htmx_delete_ticket'),
    path('htmx/save-notes/<int:report_id>/', htmx_save_notes, name='htmx_save_notes'),
    path('htmx/metric-score/<int:metric_id>/', htmx_update_metric_score, name='htmx_update_metric_score'),
    path('htmx/metric-note/<int:metric_id>/', htmx_save_metric_note, name='htmx_save_metric_note'),
    path('htmx/staff-tickets/<int:staff_id>/', htmx_staff_tickets, name='htmx_staff_tickets'),

    # SCHEDULER
    path('scheduler/', scheduler_dashboard_view, name='scheduler_dashboard'),
    path('scheduler/add/', htmx_add_schedule_slot, name='htmx_add_schedule_slot'),
    path('scheduler/move/<int:slot_id>/', htmx_move_schedule_slot, name='htmx_move_schedule_slot'),
    path('scheduler/delete/<int:slot_id>/', htmx_delete_schedule_slot, name='htmx_delete_schedule_slot'),
    path('scheduler/approval/<int:log_id>/<str:action>/', scheduler_approval_landing, name='scheduler_approval_landing'),
    path('scheduler/finalize/<int:log_id>/', scheduler_finalize_approval, name='scheduler_finalize_approval'),
    path('scheduler/history/', scheduler_history_view, name='scheduler_history'),

    # CHECK FORMS
    path('checkforms/', checkform_admin_view, name='checkform_admin'),
    path('checkforms/builder/', checkform_builder_view, name='checkform_builder'),
    path('checkforms/share/', checkform_share_view, name='checkform_share'),
    path('checkforms/view/<uuid:token>/', checkform_external_view, name='checkform_external'),
    path('checkforms/submit/<uuid:token>/', checkform_submit_view, name='checkform_submit'),
    
    # DELETE ACTIONS
    path('settings/delete/<str:model_type>/<int:item_id>/', delete_setting_item, name='delete_setting_item'),
    path('staff/note/delete/<int:note_id>/', delete_staff_note, name='delete_staff_note'),
    path('staff/warning/delete/<int:warning_id>/', delete_staff_warning, name='delete_staff_warning'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)