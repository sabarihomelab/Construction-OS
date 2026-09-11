package com.constructionos.app.core.projects

import android.content.Context

class ProjectSelectionStore(context: Context) {
    private val preferences = context.getSharedPreferences(
        "construction-os-project-selection",
        Context.MODE_PRIVATE,
    )

    fun selectedProjectId(organizationId: String): String? =
        preferences.getString(key(organizationId), null)

    fun select(organizationId: String, projectId: String) {
        preferences.edit().putString(key(organizationId), projectId).apply()
    }

    fun clear(organizationId: String) {
        preferences.edit().remove(key(organizationId)).apply()
    }

    private fun key(organizationId: String): String = "selected-project:$organizationId"
}
