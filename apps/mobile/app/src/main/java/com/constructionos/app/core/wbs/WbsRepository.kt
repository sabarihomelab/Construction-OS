package com.constructionos.app.core.wbs

import com.constructionos.app.core.database.WbsDao
import com.constructionos.app.core.database.WbsEntity
import com.constructionos.app.core.network.WbsApi
import com.constructionos.app.core.network.WbsTreeResponse
import kotlinx.coroutines.flow.Flow

class WbsRepository(
    private val api: WbsApi,
    private val dao: WbsDao,
) {
    fun observe(projectId: String, query: String): Flow<List<WbsEntity>> =
        if (query.isBlank()) dao.observeTree(projectId) else dao.search(projectId, query.trim())

    suspend fun refresh(projectId: String) {
        val rows = api.wbsTree(projectId).mapIndexed { index, response ->
            response.toEntity(index)
        }
        dao.replaceProject(projectId, rows)
    }
}

private fun WbsTreeResponse.toEntity(treeOrder: Int): WbsEntity = WbsEntity(
    id = id,
    organizationId = organizationId,
    projectId = projectId,
    parentId = parentId,
    code = code,
    name = name,
    kind = kind,
    status = status,
    description = description,
    revision = revision,
    depth = depth,
    pathCodes = pathCodes.joinToString(" / "),
    childCount = childCount,
    treeOrder = treeOrder,
)
