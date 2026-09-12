package com.constructionos.app.core.offline

import com.constructionos.app.core.attendance.AttendanceMutationSyncService
import com.constructionos.app.core.attendance.AttendanceRepository
import com.constructionos.app.core.database.ProjectEntity
import com.constructionos.app.core.dpr.DprMutationSyncService
import com.constructionos.app.core.dpr.DprPhotoSyncService
import com.constructionos.app.core.dpr.DprRepository
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
    private val attendanceMutationSyncService: AttendanceMutationSyncService,
    private val dprRepository: DprRepository,
    private val dprMutationSyncService: DprMutationSyncService,
    private val dprPhotoSyncService: DprPhotoSyncService,
) {
    suspend fun syncNow() {
        val context = api.sessionContext()
        deviceRegistrar.register()

        attendanceMutationSyncService.drain()
        dprMutationSyncService.drain()
        dprPhotoSyncService.drain()

        val projects = projectRepository.refresh(context.organizationId)
        projects.forEach { project ->
            val today = attendanceDateFor(project)
            if (context.canUseAttendance(project.id)) {
                attendanceRepository.refreshRoster(
                    projectId = project.id,
                    attendanceDate = today,
                )
            }
            if (context.canViewAttendance(project.id)) {
                attendanceRepository.refreshDay(
                    projectId = project.id,
                    attendanceDate = today,
                )
            }
            if (context.canViewDpr(project.id)) {
                dprRepository.refreshProject(project.id)
            }
        }

        attendanceMutationSyncService.drain()
        dprMutationSyncService.drain()
        dprPhotoSyncService.drain()
    }
}

internal fun SessionContextResponse.canUseAttendance(projectId: String): Boolean {
    val mobileWorkforceEnabled = features.any { it.key == "workforce" && it.mobileEnabled }
    if (!mobileWorkforceEnabled) return false
    return allowsProjectPermission(
        projectId,
        "workforce.attendance.view",
        "workforce.attendance.create",
        "workforce.attendance.update",
    )
}

internal fun SessionContextResponse.canViewAttendance(projectId: String): Boolean =
    features.any { it.key == "workforce" && it.mobileEnabled } &&
        allowsProjectPermission(projectId, "workforce.attendance.view")

internal fun SessionContextResponse.canViewDpr(projectId: String): Boolean =
    features.any { it.key == "field" && it.mobileEnabled } &&
        allowsProjectPermission(projectId, "field.daily_report.view")

private fun SessionContextResponse.allowsProjectPermission(
    projectId: String,
    vararg keys: String,
): Boolean {
    val organizationGrants = permissions.toSet()
    val projectGrants = projectPermissions[projectId].orEmpty().toSet()
    return keys.any { it in organizationGrants || it in projectGrants }
}

internal fun attendanceDateFor(project: ProjectEntity): String {
    val zoneId = project.timezone
        ?.let { timezone -> runCatching { ZoneId.of(timezone) }.getOrNull() }
        ?: ZoneId.systemDefault()
    return LocalDate.now(zoneId).toString()
}
