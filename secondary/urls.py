from django.urls import path

from secondary import views


app_name = "secondary"


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("policies/", views.policy_list, name="policy_list"),
    path("policies/<int:policy_id>/grade-bands/", views.policy_grade_bands, name="policy_grade_bands"),
    path("competencies/", views.competency_list, name="competency_list"),
    path("subject-competencies/", views.subject_competency_list, name="subject_competency_list"),
    path("subject-enrollments/", views.subject_enrollment_list, name="subject_enrollment_list"),
    path("ca-tasks/", views.ca_task_list, name="ca_task_list"),
    path("ca-tasks/<int:task_id>/records/", views.ca_task_records, name="ca_task_records"),
    path("moderation/", views.moderation_queue, name="moderation_queue"),
    path("exams/", views.exam_list, name="exam_list"),
    path("exams/<int:assessment_id>/marks/", views.exam_marks, name="exam_marks"),
    path("uneb-batches/", views.uneb_batch_list, name="uneb_batch_list"),
    path("uneb-batches/<int:batch_id>/", views.uneb_batch_detail, name="uneb_batch_detail"),
    path("uneb-batches/<int:batch_id>/build/", views.uneb_batch_build, name="uneb_batch_build"),
    path("uneb-batches/<int:batch_id>/lock/", views.uneb_batch_lock, name="uneb_batch_lock"),
    path("report-preview/", views.report_preview, name="report_preview"),
    path("cbc-term-report/", views.cbc_term_report, name="cbc_term_report"),
    path("cbc-term-report/pdf/", views.cbc_term_report_pdf, name="cbc_term_report_pdf"),
    path("alevel/scales/", views.alevel_scales, name="alevel_scales"),
    path("alevel/component-weights/", views.alevel_component_weights, name="alevel_component_weights"),
    path("alevel/modules/", views.alevel_modules, name="alevel_modules"),
    path("alevel/assessments/", views.alevel_assessments, name="alevel_assessments"),
    path("alevel/report-preview/", views.alevel_report_preview, name="alevel_report_preview"),
    path("alevel/results/", views.alevel_result_report, name="alevel_result_report"),
]
