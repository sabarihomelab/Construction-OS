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
        DprReportEntity::class,
        DprMutationEntity::class,
        DprWorkProgressEntity::class,
        DprWbsReferenceEntity::class,
        DprBoqReferenceEntity::class,
        DprDelayEntity::class,
    ],
    version = 5,
    exportSchema = false,
)
abstract class ConstructionOsDatabase : RoomDatabase() {
    abstract fun projectDao(): ProjectDao
    abstract fun attendanceDao(): AttendanceDao
    abstract fun dprDao(): DprDao

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

        private val migration2To3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS dpr_reports (
                        id TEXT NOT NULL PRIMARY KEY,
                        server_id TEXT,
                        organization_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        report_date TEXT NOT NULL,
                        shift_code TEXT NOT NULL,
                        status TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        weather_condition TEXT,
                        temperature_low TEXT,
                        temperature_high TEXT,
                        temperature_unit TEXT,
                        notes TEXT,
                        sync_state TEXT NOT NULL,
                        server_updated_at TEXT,
                        local_updated_at INTEGER NOT NULL
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE UNIQUE INDEX IF NOT EXISTS index_dpr_reports_project_id_report_date_shift_code ON dpr_reports(project_id, report_date, shift_code)",
                )
                db.execSQL(
                    "CREATE UNIQUE INDEX IF NOT EXISTS index_dpr_reports_server_id ON dpr_reports(server_id)",
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_dpr_reports_project_id_status_report_date ON dpr_reports(project_id, status, report_date)",
                )

                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS dpr_mutations (
                        client_mutation_id TEXT NOT NULL PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        report_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
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
                    "CREATE INDEX IF NOT EXISTS index_dpr_mutations_project_id_state ON dpr_mutations(project_id, state)",
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_dpr_mutations_report_id_operation_state ON dpr_mutations(report_id, operation, state)",
                )
            }
        }

        private val migration3To4 = object : Migration(3, 4) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS dpr_work_progress (
                        id TEXT NOT NULL PRIMARY KEY,
                        report_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        position INTEGER NOT NULL,
                        wbs_code_id TEXT,
                        boq_item_id TEXT,
                        description TEXT NOT NULL,
                        location TEXT,
                        quantity TEXT,
                        unit_code TEXT,
                        progress_percent TEXT,
                        remarks TEXT
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_dpr_work_progress_report_id_position ON dpr_work_progress(report_id, position)",
                )

                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS dpr_wbs_references (
                        id TEXT NOT NULL PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        code TEXT NOT NULL,
                        name TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        parent_id TEXT
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_dpr_wbs_references_project_id_code ON dpr_wbs_references(project_id, code)",
                )

                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS dpr_boq_references (
                        id TEXT NOT NULL PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        boq_id TEXT NOT NULL,
                        boq_code TEXT NOT NULL,
                        boq_name TEXT NOT NULL,
                        wbs_code_id TEXT,
                        item_code TEXT NOT NULL,
                        description TEXT NOT NULL,
                        unit_code TEXT NOT NULL
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_dpr_boq_references_project_id_boq_code_item_code ON dpr_boq_references(project_id, boq_code, item_code)",
                )
            }
        }

        private val migration4To5 = object : Migration(4, 5) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS dpr_delays (
                        id TEXT NOT NULL PRIMARY KEY,
                        report_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        position INTEGER NOT NULL,
                        category TEXT,
                        description TEXT NOT NULL,
                        started_at TEXT,
                        ended_at TEXT,
                        lost_hours TEXT,
                        responsible_party TEXT,
                        schedule_impact INTEGER NOT NULL,
                        notes TEXT
                    )
                    """.trimIndent(),
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS index_dpr_delays_report_id_position ON dpr_delays(report_id, position)",
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
                    .addMigrations(migration1To2, migration2To3, migration3To4, migration4To5)
                    .build()
                    .also { instance = it }
            }
    }
}
