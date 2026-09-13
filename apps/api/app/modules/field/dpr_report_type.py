from app.modules.reporting.type_registry import (
    AttachmentPolicy,
    LocationStampPolicy,
    ReportGenerationTrigger,
    ReportScopeKind,
    ReportTypeContract,
    report_types,
)

DPR_REPORT_TYPE_KEY = "field.dpr"


if not report_types.contains(DPR_REPORT_TYPE_KEY):
    report_types.register(
        ReportTypeContract(
            key=DPR_REPORT_TYPE_KEY,
            name="Daily Progress Report",
            scopes=(ReportScopeKind.PROJECT,),
            allowed_triggers=(
                ReportGenerationTrigger.MANUAL,
                ReportGenerationTrigger.ON_APPROVAL,
                ReportGenerationTrigger.DAILY,
            ),
            default_trigger=ReportGenerationTrigger.ON_APPROVAL,
            attachment_policy=AttachmentPolicy.OPTIONAL,
            location_stamp_policy=LocationStampPolicy.OPTIONAL,
            supports_photos=True,
            supports_signatures=True,
            supports_section_selection=True,
            stores_issued_output=True,
            issued_output_formats=("pdf", "docx"),
            default_output_format="pdf",
            filename_pattern="{{project.number}}-DPR-{{report.date}}-{{report.shift}}-R{{report.revision}}",
            required_permission_key="field.daily_report.view",
        )
    )
