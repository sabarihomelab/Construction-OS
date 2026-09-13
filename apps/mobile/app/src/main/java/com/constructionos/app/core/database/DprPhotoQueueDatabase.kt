package com.constructionos.app.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import java.security.MessageDigest

@Database(
    entities = [DprPhotoEntity::class],
    version = 3,
    exportSchema = false,
)
abstract class DprPhotoQueueDatabase : RoomDatabase() {
    abstract fun dprPhotoDao(): DprPhotoDao

    companion object {
        private val instances = mutableMapOf<String, DprPhotoQueueDatabase>()

        private val migration1To2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "ALTER TABLE dpr_photos ADD COLUMN uploaded_bytes INTEGER NOT NULL DEFAULT 0",
                )
                db.execSQL(
                    "ALTER TABLE dpr_photos ADD COLUMN chunk_size_bytes INTEGER NOT NULL DEFAULT 5242880",
                )
            }
        }

        private val migration2To3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE dpr_photos ADD COLUMN upload_path TEXT")
                db.execSQL(
                    "ALTER TABLE dpr_photos ADD COLUMN upload_policy TEXT NOT NULL DEFAULT 'legacy_original'",
                )
            }
        }

        fun getInstance(
            context: Context,
            connectionNamespace: String,
        ): DprPhotoQueueDatabase = synchronized(this) {
            instances[connectionNamespace] ?: Room.databaseBuilder(
                context.applicationContext,
                DprPhotoQueueDatabase::class.java,
                databaseName(connectionNamespace),
            )
                .addMigrations(migration1To2, migration2To3)
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
