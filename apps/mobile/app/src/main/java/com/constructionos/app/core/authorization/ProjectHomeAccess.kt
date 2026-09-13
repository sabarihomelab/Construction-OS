package com.constructionos.app.core.authorization

import com.constructionos.app.core.network.SessionContextResponse

enum class ProjectHomeActionKey {
    ATTENDANCE,
    DAILY_REPORT,
}

enum class ProjectActionMode {
    WORK,
    REVIEW,
    VIEW,
}

data class ProjectHomeAction(
    val key: ProjectHomeActionKey,
    val title: String,
    val subtitle: String,
    val mode: ProjectActionMode,
)

fun SessionContextResponse.projectHomeActions(projectId: String): List<ProjectHomeAction> {
    val mobileFeatures = features
        .asSequence()
        .filter { it.mobileEnabled }
        .map { it.key }
        .toSet()
    val grants = permissions.toSet() + projectPermissions[projectId].orEmpty()

    fun has(permission: String): Boolean = permission in grants
    fun allowsAny(vararg permissionKeys: String): Boolean = permissionKeys.any(::has)

    return buildList {
        if (
            "workforce" in mobileFeatures &&
            allowsAny(
                "workforce.attendance.view",
                "workforce.attendance.create",
                "workforce.attendance.update",
                "workforce.attendance.submit",
                "workforce.attendance.approve",
                "workforce.attendance.reopen",
            )
        ) {
            val mode = when {
                allowsAny(
                    "workforce.attendance.create",
                    "workforce.attendance.update",
                    "workforce.attendance.submit",
                ) -> ProjectActionMode.WORK

                allowsAny(
                    "workforce.attendance.approve",
                    "workforce.attendance.reopen",
                ) -> ProjectActionMode.REVIEW

                else -> ProjectActionMode.VIEW
            }
            add(
                ProjectHomeAction(
                    key = ProjectHomeActionKey.ATTENDANCE,
                    title = "Attendance",
                    subtitle = when (mode) {
                        ProjectActionMode.WORK -> "Record crew attendance and prepare today's register"
                        ProjectActionMode.REVIEW -> "Review submitted attendance and exceptions"
                        ProjectActionMode.VIEW -> "View crew attendance for this project"
                    },
                    mode = mode,
                ),
            )
        }

        if (
            "field" in mobileFeatures &&
            allowsAny(
                "field.daily_report.view",
                "field.daily_report.create",
                "field.daily_report.update",
                "field.daily_report.submit",
                "field.daily_report.approve",
                "field.daily_report.manage",
            )
        ) {
            val mode = when {
                allowsAny(
                    "field.daily_report.create",
                    "field.daily_report.update",
                    "field.daily_report.submit",
                ) -> ProjectActionMode.WORK

                allowsAny(
                    "field.daily_report.approve",
                    "field.daily_report.manage",
                ) -> ProjectActionMode.REVIEW

                else -> ProjectActionMode.VIEW
            }
            add(
                ProjectHomeAction(
                    key = ProjectHomeActionKey.DAILY_REPORT,
                    title = "Daily report",
                    subtitle = when (mode) {
                        ProjectActionMode.WORK -> "Capture progress, notes, delays and site records"
                        ProjectActionMode.REVIEW -> "Review submitted daily reports and exceptions"
                        ProjectActionMode.VIEW -> "View daily reports for this project"
                    },
                    mode = mode,
                ),
            )
        }
    }
}

fun SessionContextResponse.hasProjectPermission(projectId: String, permission: String): Boolean =
    permission in permissions || permission in projectPermissions[projectId].orEmpty()
