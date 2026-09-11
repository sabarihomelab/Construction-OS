package com.constructionos.app.core.offline

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

class WorkspaceSyncScheduler(context: Context) {
    private val workManager = WorkManager.getInstance(context.applicationContext)
    private val networkConstraints = Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)
        .build()

    fun schedule() {
        val immediate = OneTimeWorkRequestBuilder<WorkspaceSyncWorker>()
            .setConstraints(networkConstraints)
            .build()
        workManager.enqueueUniqueWork(
            IMMEDIATE_WORK,
            ExistingWorkPolicy.REPLACE,
            immediate,
        )

        val periodic = PeriodicWorkRequestBuilder<WorkspaceSyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(networkConstraints)
            .build()
        workManager.enqueueUniquePeriodicWork(
            PERIODIC_WORK,
            ExistingPeriodicWorkPolicy.KEEP,
            periodic,
        )
    }

    fun cancel() {
        workManager.cancelUniqueWork(IMMEDIATE_WORK)
        workManager.cancelUniqueWork(PERIODIC_WORK)
    }

    companion object {
        private const val IMMEDIATE_WORK = "workspace-sync-now"
        private const val PERIODIC_WORK = "workspace-sync-periodic"
    }
}
