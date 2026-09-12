package com.constructionos.app.core.dpr

import java.util.Collections
import java.util.WeakHashMap

private val photoBindings = Collections.synchronizedMap(
    WeakHashMap<DprRepository, DprPhotoRepository>(),
)

fun DprRepository.bindPhotoRepository(repository: DprPhotoRepository) {
    photoBindings[this] = repository
}

fun DprRepository.requirePhotoRepository(): DprPhotoRepository =
    requireNotNull(photoBindings[this]) { "DPR photo repository is not available for this workspace." }
