package com.constructionos.app.core.dpr

import java.util.Collections
import java.util.WeakHashMap

private val customFieldBindings = Collections.synchronizedMap(
    WeakHashMap<DprRepository, DprCustomFieldRepository>(),
)

fun DprRepository.bindCustomFieldRepository(repository: DprCustomFieldRepository) {
    customFieldBindings[this] = repository
}

fun DprRepository.requireCustomFieldRepository(): DprCustomFieldRepository =
    requireNotNull(customFieldBindings[this]) {
        "DPR custom field repository is not available for this workspace."
    }
