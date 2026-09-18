package com.constructionos.app.core.dpr

import java.util.Collections
import java.util.WeakHashMap

private val attendanceSummaryBindings = Collections.synchronizedMap(
    WeakHashMap<DprRepository, DprAttendanceSummaryRepository>(),
)

fun DprRepository.bindAttendanceSummaryRepository(repository: DprAttendanceSummaryRepository) {
    attendanceSummaryBindings[this] = repository
}

fun DprRepository.requireAttendanceSummaryRepository(): DprAttendanceSummaryRepository =
    requireNotNull(attendanceSummaryBindings[this]) {
        "DPR attendance summary repository is not available for this workspace."
    }
