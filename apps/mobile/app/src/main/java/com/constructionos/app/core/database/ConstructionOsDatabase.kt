package com.constructionos.app.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [ProjectEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class ConstructionOsDatabase : RoomDatabase() {
    abstract fun projectDao(): ProjectDao

    companion object {
        @Volatile
        private var instance: ConstructionOsDatabase? = null

        fun getInstance(context: Context): ConstructionOsDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    ConstructionOsDatabase::class.java,
                    "construction-os.db",
                ).build().also { instance = it }
            }
    }
}
