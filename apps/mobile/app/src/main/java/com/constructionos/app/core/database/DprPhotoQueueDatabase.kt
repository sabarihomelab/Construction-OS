package com.constructionos.app.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import java.security.MessageDigest

@Database(
    entities = [DprPhotoEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class DprPhotoQueueDatabase : RoomDatabase() {
    abstract fun dprPhotoDao(): DprPhotoDao

    companion object {
        private val instances = mutableMapOf<String, DprPhotoQueueDatabase>()

        fun getInstance(
            context: Context,
            connectionNamespace: String,
        ): DprPhotoQueueDatabase = synchronized(this) {
            instances[connectionNamespace] ?: Room.databaseBuilder(
                context.applicationContext,
                DprPhotoQueueDatabase::class.java,
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
            return "construction-os-dpr-photos-$suffix.db"
        }
    }
}
