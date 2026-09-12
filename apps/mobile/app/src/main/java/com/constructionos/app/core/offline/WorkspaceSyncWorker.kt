package com.constructionos.app.core.offline

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.constructionos.app.core.AppContainer
import com.constructionos.app.core.deployment.WorkspaceConnectionStore
import java.io.IOException
import retrofit2.HttpException

class WorkspaceSyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val requestedNamespace = inputData.getString(
            WorkspaceConnectionStore.WORKER_CONNECTION_NAMESPACE,
        ) ?: return Result.success()
        val connection = WorkspaceConnectionStore(applicationContext).current()
            ?: return Result.success()
        if (connection.localNamespace != requestedNamespace) return Result.success()

        return try {
            AppContainer(applicationContext, connection).workspaceSyncService.syncNow()
            Result.success()
        } catch (error: HttpException) {
            when {
                error.code() == 401 -> Result.success()
                error.code() in 500..599 -> Result.retry()
                else -> Result.failure()
            }
        } catch (_: IOException) {
            Result.retry()
        }
    }
}
