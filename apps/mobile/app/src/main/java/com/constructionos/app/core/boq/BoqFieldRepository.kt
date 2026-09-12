package com.constructionos.app.core.boq

import com.constructionos.app.core.database.BoqFieldDao
import com.constructionos.app.core.database.BoqFieldEntity
import com.constructionos.app.core.network.BoqFieldApi
import com.constructionos.app.core.network.BoqFieldReferenceResponse
import kotlinx.coroutines.flow.Flow

class BoqFieldRepository(
    private val api: BoqFieldApi,
    private val dao: BoqFieldDao,
) {
    fun observe(projectId: String, query: String): Flow<List<BoqFieldEntity>> =
        if (query.isBlank()) dao.observe(projectId) else dao.search(projectId, query.trim())

    suspend fun refresh(projectId: String) {
        val rows = api.fieldReferences(projectId).mapIndexed { index, response ->
            response.toEntity(projectId, index)
        }
        dao.replaceProject(projectId, rows)
    }
}

private fun BoqFieldReferenceResponse.toEntity(
    projectId: String,
    sortOrder: Int,
): BoqFieldEntity = BoqFieldEntity(
    itemId = itemId,
    projectId = projectId,
    boqId = boqId,
    boqCode = boqCode,
    boqName = boqName,
    boqRevision = boqRevision,
    wbsCodeId = wbsCodeId,
    lineNumber = lineNumber,
    itemCode = itemCode,
    description = description,
    unitCode = unitCode,
    quantity = quantity,
    itemRevision = itemRevision,
    sortOrder = sortOrder,
)
