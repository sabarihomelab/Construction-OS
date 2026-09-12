package com.constructionos.app.core.offline

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import com.constructionos.app.core.deployment.WorkspaceConnectionStore

class WorkspaceSyncScheduler(
    context: Context,
    private val deploymentId: String,
) {
    private val applicationContext = context.applicationContext
    private val workManager = WorkManager.getInstance(applicationContext)
    private val connectivityManager = applicationContext.getSystemService(ConnectivityManager::class.java)
    private val networkConstraints = Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)
        .build()

    fun isNetworkAvailable(): Boolean {
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    fun scheduleOnce() {
        disableLegacySync()
        val request = OneTimeWorkRequestBuilder<WorkspaceSyncWorker>()
            .setConstraints(networkConstraints)
            .setInputData(
                workDataOf(
                    WorkspaceConnectionStore.WORKER_DEPLOYMENT_ID to deploymentId,
                ),
            )
            .build()
        workManager.enqueueUniqueWork(
            oneTimeWorkName(),
            ExistingWorkPolicy.REPLACE,
            request,
        )
    }

    fun disableLegacyPeriodicSync() {
        workManager.cancelUniqueWork(LEGACY_PERIODIC_WORK)
    }

    fun cancel() {
        workManager.cancelUniqueWork(oneTimeWorkName())
        disableLegacySync()
    }

    private fun disableLegacySync() {
        workManager.cancelUniqueWork(LEGACY_ONE_TIME_WORK)
        disableLegacyPeriodicSync()
    }

    private fun oneTimeWorkName(): String = "$ONE_TIME_WORK_PREFIX:$deploymentId"

    companion object {
        private const val ONE_TIME_WORK_PREFIX = "workspace-sync-now"
        private const val LEGACY_ONE_TIME_WORK = "workspace-sync-now"
        private const val LEGACY_PERIODIC_WORK = "workspace-sync-periodic"
    }
}
