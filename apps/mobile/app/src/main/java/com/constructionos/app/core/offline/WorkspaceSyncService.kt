package com.constructionos.app.core.offline

import com.constructionos.app.core.attendance.AttendanceRepository
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.SessionContextResponse
import com.constructionos.app.core.projects.ProjectRepository
import java.time.LocalDate
import java.time.ZoneId

class WorkspaceSyncService(
    private val api: ConstructionOsApi,
    private val deviceRegistrar: DeviceRegistrar,
    private val projectRepository: ProjectRepository,
    private val attendanceRepository: AttendanceRepository,
) {
    suspend fun syncNow() {
        val context = api.sessionContext()
        deviceRegistrar.register()
        val projects = projectRepository.refresh(context.organizationId)
        projects
            .asSequence()
            .filter { context.canViewAttendance(it.id) }
            .forEach { project ->
                attendanceRepository.refreshRoster(
                    projectId = project.id,
                    attendanceDate = attendanceDateFor(project),
                )
            }
    }
}

internal fun SessionContextResponse.canViewAttendance(projectId: String): Boolean {
    val mobileWorkforceEnabled = features.any { it.key == "workforce" && it.mobileEnabled }
    if (!mobileWorkforceEnabled) {
        return false
    }
    val permission = "workforce.attendance.view"
    return permission in permissions || permission in projectPermissions[projectId].orEmpty()
}

internal fun attendanceDateFor(project: ProjectEntity): String {
    val zoneId = project.timezone
        ?.let { runCatching(ZoneId::of).getOrNull() }
        ?: ZoneId.systemDefault()
    return LocalDate.now(zoneId).toString()
}
