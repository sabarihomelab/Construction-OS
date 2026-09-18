package com.constructionos.app.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import java.security.MessageDigest

@Database(
    entities = [DprAttendanceSummaryEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class DprAttendanceSummaryDatabase : RoomDatabase() {
    abstract fun dprAttendanceSummaryDao(): DprAttendanceSummaryDao

    companion object {
        private val instances = mutableMapOf<String, DprAttendanceSummaryDatabase>()

        fun getInstance(
            context: Context,
            connectionNamespace: String,
        ): DprAttendanceSummaryDatabase = synchronized(this) {
            instances[connectionNamespace] ?: Room.databaseBuilder(
                context.applicationContext,
                DprAttendanceSummaryDatabase::class.java,
                databaseName(connectionNamespace),
            )
                .build()
                .also { instances[connectionNamespace] = it }
        }

        private fun databaseName(connectionNamespace: String): String {
            val digest = MessageDigest.getInstance("SHA-256")
                .digest(connectionNamespace.toByteArray(Charsets.UTF_8))
            val suffix = digest.take(12).joinToString("") {
                "%02x".format(it.toInt() and 0xff)
            }
            return "construction-os-dpr-attendance-$suffix.db"
        }
    }
}
