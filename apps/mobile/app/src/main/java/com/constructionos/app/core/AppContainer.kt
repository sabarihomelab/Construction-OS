package com.constructionos.app.core

import android.content.Context
import com.constructionos.app.core.attendance.AttendanceMutationSyncService
import com.constructionos.app.core.attendance.AttendanceRepository
import com.constructionos.app.core.auth.AuthController
import com.constructionos.app.core.authorization.AccessAdminRepository
import com.constructionos.app.core.authorization.ProjectAccessAdminRepository
import com.constructionos.app.core.boq.BoqFieldRepository
import com.constructionos.app.core.database.ConstructionOsDatabase
import com.constructionos.app.core.database.DprPhotoQueueDatabase
import com.constructionos.app.core.deployment.WorkspaceConnection
import com.constructionos.app.core.dpr.DprLifecycleRepository
import com.constructionos.app.core.dpr.DprMutationSyncService
import com.constructionos.app.core.dpr.DprPhotoRepository
import com.constructionos.app.core.dpr.DprPhotoSyncService
import com.constructionos.app.core.dpr.DprRepository
import com.constructionos.app.core.estimating.EstimatingReviewRepository
import com.constructionos.app.core.network.NetworkFactory
import com.constructionos.app.core.offline.DeviceRegistrar
import com.constructionos.app.core.offline.WorkspaceSyncScheduler
import com.constructionos.app.core.offline.WorkspaceSyncService
import com.constructionos.app.core.parties.PartyRepository
import com.constructionos.app.core.projects.ProjectRepository
import com.constructionos.app.core.projects.ProjectSelectionStore
import com.constructionos.app.core.session.SecureSessionStore
import com.constructionos.app.core.wbs.WbsRepository
import com.constructionos.app.core.workforce.WorkforceRepository
import com.constructionos.app.core.workspace.WorkspaceCoordinator

class AppContainer(
    context: Context,
    connection: WorkspaceConnection,
) {
    private val applicationContext = context.applicationContext
    private val localNamespace = connection.localNamespace
    private val sessionStore = SecureSessionStore(applicationContext, localNamespace)
    private val api = NetworkFactory.createApi(connection.apiBaseUrl, sessionStore)
    private val wbsApi = NetworkFactory.createWbsApi(connection.apiBaseUrl, sessionStore)
    private val boqFieldApi = NetworkFactory.createBoqFieldApi(connection.apiBaseUrl, sessionStore)
    private val estimatingApi = NetworkFactory.createEstimatingApi(connection.apiBaseUrl, sessionStore)
    private val workforceApi = NetworkFactory.createWorkforceApi(connection.apiBaseUrl, sessionStore)
    private val dprLifecycleApi = NetworkFactory.createDprLifecycleApi(connection.apiBaseUrl, sessionStore)
    private val dprPhotoApi = NetworkFactory.createDprPhotoApi(connection.apiBaseUrl, sessionStore)
    private val database = ConstructionOsDatabase.getInstance(
        applicationContext,
        localNamespace,
    )
    private val dprPhotoDatabase = DprPhotoQueueDatabase.getInstance(
        applicationContext,
        localNamespace,
    )
    private val projectRepository = ProjectRepository(api, database.projectDao())
    private val projectSelectionStore = ProjectSelectionStore(
        applicationContext,
        localNamespace,
    )
    private val deviceRegistrar = DeviceRegistrar(applicationContext, api)
    private val syncScheduler = WorkspaceSyncScheduler(
        applicationContext,
        localNamespace,
    )

    val accessAdminRepository = AccessAdminRepository(api)
    val projectAccessAdminRepository = ProjectAccessAdminRepository(api)

    val attendanceRepository = AttendanceRepository(
        api = api,
        dao = database.attendanceDao(),
        deviceRegistrar = deviceRegistrar,
        syncScheduler = syncScheduler,
    )

    private val attendanceMutationSyncService = AttendanceMutationSyncService(
        api = api,
        dao = database.attendanceDao(),
        deviceRegistrar = deviceRegistrar,
    )

    val dprRepository = DprRepository(
        api = api,
        dao = database.dprDao(),
        syncScheduler = syncScheduler,
    )

    val dprLifecycleRepository = DprLifecycleRepository(
        api = dprLifecycleApi,
        dao = database.dprDao(),
        syncScheduler = syncScheduler,
        cacheDir = applicationContext.cacheDir,
    )

    val dprPhotoRepository = DprPhotoRepository(
        context = applicationContext,
        connectionNamespace = localNamespace,
        api = dprPhotoApi,
        photoDao = dprPhotoDatabase.dprPhotoDao(),
        dprDao = database.dprDao(),
        syncScheduler = syncScheduler,
    )

    private val dprMutationSyncService = DprMutationSyncService(
        api = api,
        dao = database.dprDao(),
        deviceRegistrar = deviceRegistrar,
    )

    private val dprPhotoSyncService = DprPhotoSyncService(
        api = dprPhotoApi,
        photoDao = dprPhotoDatabase.dprPhotoDao(),
        dprDao = database.dprDao(),
        dprRepository = dprRepository,
    )

    val partyRepository = PartyRepository(
        api = api,
        dao = database.partyDao(),
    )

    val wbsRepository = WbsRepository(
        api = wbsApi,
        dao = database.wbsDao(),
    )

    val boqFieldRepository = BoqFieldRepository(
        api = boqFieldApi,
        dao = database.boqFieldDao(),
    )

    val estimatingReviewRepository = EstimatingReviewRepository(
        api = estimatingApi,
    )

    val workforceRepository = WorkforceRepository(
        api = workforceApi,
        dao = database.workforceDao(),
    )

    val authController = AuthController(
        api = api,
        sessionStore = sessionStore,
    )

    val workspaceSyncService = WorkspaceSyncService(
        api = api,
        deviceRegistrar = deviceRegistrar,
        projectRepository = projectRepository,
        attendanceRepository = attendanceRepository,
        attendanceMutationSyncService = attendanceMutationSyncService,
        dprRepository = dprRepository,
        dprMutationSyncService = dprMutationSyncService,
        dprPhotoSyncService = dprPhotoSyncService,
    )

    val workspaceCoordinator = WorkspaceCoordinator(
        repository = projectRepository,
        selectionStore = projectSelectionStore,
        syncScheduler = syncScheduler,
        syncService = workspaceSyncService,
    )
}
