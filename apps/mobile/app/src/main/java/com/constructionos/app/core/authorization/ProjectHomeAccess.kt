package com.constructionos.app.core.authorization

import com.constructionos.app.core.network.SessionContextResponse

enum class ProjectHomeActionKey {
    ATTENDANCE,
    DAILY_REPORT,
}

data class ProjectHomeAction(
    val key: ProjectHomeActionKey,
    val title: String,
    val subtitle: String,
)

fun SessionContextResponse.projectHomeActions(projectId: String): List<ProjectHomeAction> {
    val mobileFeatures = features
        .asSequence()
        .filter { it.mobileEnabled }
        .map { it.key }
        .toSet()
    val projectGrants = projectPermissions[projectId].orEmpty().toSet()
    val organizationGrants = permissions.toSet()

    fun allowsAny(vararg keys: String): Boolean = keys.any {
        it in organizationGrants || it in projectGrants
    }

    return buildList {
        if (
            "workforce" in mobileFeatures &&
            allowsAny(
                "workforce.attendance.view",
                "workforce.attendance.create",
                "workforce.attendance.update",
            )
        ) {
            add(
                ProjectHomeAction(
                    key = ProjectHomeActionKey.ATTENDANCE,
                    title = "Attendance",
                    subtitle = "Crew attendance and time for this project",
                ),
            )
        }

        if (
            "field" in mobileFeatures &&
            allowsAny(
                "field.daily_report.view",
                "field.daily_report.create",
                "field.daily_report.update",
            )
        ) {
            add(
                ProjectHomeAction(
                    key = ProjectHomeActionKey.DAILY_REPORT,
                    title = "Daily progress report",
                    subtitle = "Work progress, notes, delays and site records",
                ),
            )
        }
    }
}
