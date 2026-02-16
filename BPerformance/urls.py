from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from core.views import export_staff_pdf_view

# Import views from your 'core' app
from core.views import (
    dashboard_view, daily_report_view, manage_settings_view,
    htmx_add_ticket, htmx_save_notes, htmx_get_edit_form, htmx_save_ticket,
    htmx_update_metric_score, htmx_save_metric_note, htmx_delete_ticket,
    report_archive_view, mark_report_submitted, generate_pdf_view,
    staff_index_view, staff_detail_view, send_weekly_report_view,
    delete_setting_item, delete_staff_note, delete_staff_warning
)

urlpatterns = [
    # ADMIN
    path('admin/', admin.site.urls),

    # AUTHENTICATION
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # DASHBOARD & REPORTS
    path('', dashboard_view, name='dashboard'),
    path('report/', daily_report_view, name='daily_report'),
    path('report/<str:date_str>/', daily_report_view, name='daily_report_date'),
    path('archive/', report_archive_view, name='report_archive'),
    path('report/submit/<int:report_id>/', mark_report_submitted, name='mark_submitted'),
    path('report/pdf/<int:report_id>/', generate_pdf_view, name='generate_pdf'),
    path('report/send-weekly/', send_weekly_report_view, name='send_weekly_report'),
    path('staff/export/<int:staff_id>/', export_staff_pdf_view, name='export_staff_pdf'),

    # SETTINGS & STAFF
    path('settings/', manage_settings_view, name='settings'),
    path('staff/', staff_index_view, name='staff_index'),
    path('staff/<int:staff_id>/', staff_detail_view, name='staff_detail'),

    # HTMX (DYNAMIC ACTIONS)
    path('htmx/add-ticket/<int:report_id>/', htmx_add_ticket, name='htmx_add_ticket'),
    path('htmx/edit-ticket/<int:ticket_id>/', htmx_get_edit_form, name='htmx_get_edit_form'),
    path('htmx/save-ticket/<int:ticket_id>/', htmx_save_ticket, name='htmx_save_ticket'),
    path('htmx/delete-ticket/<int:ticket_id>/', htmx_delete_ticket, name='htmx_delete_ticket'),
    path('htmx/save-notes/<int:report_id>/', htmx_save_notes, name='htmx_save_notes'),
    path('htmx/metric-score/<int:metric_id>/', htmx_update_metric_score, name='htmx_update_metric_score'),
    path('htmx/metric-note/<int:metric_id>/', htmx_save_metric_note, name='htmx_save_metric_note'),

    # DELETE ACTIONS
    path('settings/delete/<str:model_type>/<int:item_id>/', delete_setting_item, name='delete_setting_item'),
    path('staff/note/delete/<int:note_id>/', delete_staff_note, name='delete_staff_note'),
    path('staff/warning/delete/<int:warning_id>/', delete_staff_warning, name='delete_staff_warning'),
]

# --- IMAGE SERVING CONFIGURATION ---
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)