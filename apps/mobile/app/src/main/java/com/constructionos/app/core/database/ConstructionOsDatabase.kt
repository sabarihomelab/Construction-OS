package com.constructionos.app.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [
        ProjectEntity::class,
        AttendanceRosterEntity::class,
        AttendanceRegisterEntity::class,
        AttendanceEntryEntity::class,
        AttendanceMutationEntity::class,
    ],
    version = 2,
    exportSchema = false,
)
abstract class ConstructionOsDatabase : RoomDatabase() {
    abstract fun projectDao(): ProjectDao
    abstract fun attendanceDao(): AttendanceDao

    companion object {
        @Volatile
        private var instance: ConstructionOsDatabase? = null

        private val migration1To2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_roster (
                        assignment_id TEXT NOT NULL PRIMARY KEY,
                        organization_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        worker_id TEXT NOT NULL,
                        worker_number TEXT NOT NULL,
                        worker_name TEXT NOT NULL,
                        crew_id TEXT,
                        employer_party_id TEXT,
                        engagement_type TEXT,
                        status TEXT NOT NULL,
                        project_role TEXT,
                        trade TEXT,
                        default_cost_code TEXT,
                        start_date TEXT,
                        end_date TEXT,
                        revision INTEGER NOT NULL
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_attendance_roster_project_id_status ON attendance_roster(project_id, status)",
                )

                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_registers (
                        id TEXT NOT NULL PRIMARY KEY,
                        organization_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        attendance_date TEXT NOT NULL,
                        shift_code TEXT NOT NULL,
                        status TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        notes TEXT,
                        sync_state TEXT NOT NULL,
                        server_updated_at TEXT,
                        local_updated_at INTEGER NOT NULL
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE UNIQUE INDEX IF NOT EXISTS index_attendance_registers_project_id_attendance_date_shift_code ON attendance_registers(project_id, attendance_date, shift_code)",
                )

                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_entries (
                        register_id TEXT NOT NULL,
                        assignment_id TEXT NOT NULL,
                        server_entry_id TEXT,
                        project_id TEXT NOT NULL,
                        worker_id TEXT NOT NULL,
                        worker_number TEXT NOT NULL,
                        worker_name TEXT NOT NULL,
                        crew_id TEXT,
                        employer_party_id TEXT,
                        trade TEXT,
                        mark_status TEXT NOT NULL,
                        regular_hours TEXT NOT NULL,
                        overtime_hours TEXT NOT NULL,
                        wbs_code_id TEXT,
                        location TEXT,
                        notes TEXT,
                        sync_state TEXT NOT NULL,
                        local_updated_at INTEGER NOT NULL,
                        PRIMARY KEY(register_id, assignment_id)
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_attendance_entries_register_id ON attendance_entries(register_id)",
                )

                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_mutations (
                        client_mutation_id TEXT NOT NULL PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        entity_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        base_revision INTEGER,
                        payload_json TEXT NOT NULL,
                        state TEXT NOT NULL,
                        error_code TEXT,
                        attempt_count INTEGER NOT NULL,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_attendance_mutations_project_id_state ON attendance_mutations(project_id, state)",
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_attendance_mutations_entity_id_operation_state ON attendance_mutations(entity_id, operation, state)",
                )
            }
        }

        fun getInstance(context: Context): ConstructionOsDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    ConstructionOsDatabase::class.java,
                    "construction-os.db",
                )
                    .addMigrations(migration1To2)
                    .build()
                    .also { instance = it }
            }
    }
}
