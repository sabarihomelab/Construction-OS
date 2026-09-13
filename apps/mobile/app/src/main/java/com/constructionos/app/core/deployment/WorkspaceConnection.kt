package com.constructionos.app.core.deployment

import android.content.Context
import com.constructionos.app.BuildConfig
import com.constructionos.app.core.network.NetworkFactory
import java.net.URI
import java.security.MessageDigest

data class WorkspaceConnection(
    val deploymentId: String,
    val organizationId: String?,
    val organizationName: String,
    val apiBaseUrl: String,
    val environmentName: String,
) {
    val localNamespace: String
        get() {
            val material = "$apiBaseUrl|$deploymentId"
            val digest = MessageDigest.getInstance("SHA-256")
                .digest(material.toByteArray(Charsets.UTF_8))
            return digest.joinToString("") { "%02x".format(it.toInt() and 0xff) }
        }
}

class WorkspaceConnectionStore(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(
        PREFERENCES_NAME,
        Context.MODE_PRIVATE,
    )

    fun current(): WorkspaceConnection? {
        val deploymentId = preferences.getString(KEY_DEPLOYMENT_ID, null)?.takeIf { it.isNotBlank() }
            ?: return null
        val apiBaseUrl = preferences.getString(KEY_API_BASE_URL, null)?.takeIf { it.isNotBlank() }
            ?: return null
        val organizationName = preferences.getString(KEY_ORGANIZATION_NAME, null)?.takeIf { it.isNotBlank() }
            ?: return null
        val environmentName = preferences.getString(KEY_ENVIRONMENT_NAME, null)?.takeIf { it.isNotBlank() }
            ?: organizationName

        return WorkspaceConnection(
            deploymentId = deploymentId,
            organizationId = preferences.getString(KEY_ORGANIZATION_ID, null),
            organizationName = organizationName,
            apiBaseUrl = apiBaseUrl,
            environmentName = environmentName,
        )
    }

    fun save(connection: WorkspaceConnection) {
        preferences.edit()
            .putString(KEY_DEPLOYMENT_ID, connection.deploymentId)
            .putString(KEY_ORGANIZATION_ID, connection.organizationId)
            .putString(KEY_ORGANIZATION_NAME, connection.organizationName)
            .putString(KEY_API_BASE_URL, connection.apiBaseUrl)
            .putString(KEY_ENVIRONMENT_NAME, connection.environmentName)
            .apply()
    }

    fun clear() {
        preferences.edit().clear().apply()
    }

    companion object {
        const val WORKER_CONNECTION_NAMESPACE = "workspace_connection_namespace"

        private const val PREFERENCES_NAME = "construction-os-workspace-connection"
        private const val KEY_DEPLOYMENT_ID = "deployment_id"
        private const val KEY_ORGANIZATION_ID = "organization_id"
        private const val KEY_ORGANIZATION_NAME = "organization_name"
        private const val KEY_API_BASE_URL = "api_base_url"
        private const val KEY_ENVIRONMENT_NAME = "environment_name"
    }
}

class WorkspaceConnectionService {
    suspend fun connect(serverAddress: String): WorkspaceConnection {
        val apiBaseUrl = normalizeApiBaseUrl(serverAddress)
        val bootstrap = NetworkFactory.createBootstrapApi(apiBaseUrl).deploymentBootstrap()

        require(bootstrap.deploymentId.isNotBlank()) { "The server did not return a deployment ID." }
        require(bootstrap.apiPath == "/api/v1/") { "This server uses an unsupported API contract." }
        require(bootstrap.dedicatedCompany == (bootstrap.organization != null)) {
            "The server returned an invalid company binding."
        }
        if (!BuildConfig.DEBUG) {
            require(bootstrap.dedicatedCompany && bootstrap.organization != null) {
                "This Construction OS server is not bound to a company."
            }
        }

        val organizationName = bootstrap.organization?.name
            ?: bootstrap.environmentName.takeIf { it.isNotBlank() }
            ?: "Local development"

        return WorkspaceConnection(
            deploymentId = bootstrap.deploymentId,
            organizationId = bootstrap.organization?.id,
            organizationName = organizationName,
            apiBaseUrl = apiBaseUrl,
            environmentName = bootstrap.environmentName,
        )
    }

    private fun normalizeApiBaseUrl(input: String): String {
        val trimmed = input.trim().trimEnd('/')
        require(trimmed.isNotBlank()) { "Enter your company server address." }
        val candidate = if ("://" in trimmed) trimmed else "https://$trimmed"
        val uri = runCatching { URI(candidate) }
            .getOrElse { throw IllegalArgumentException("Enter a valid company server address.") }
        val scheme = uri.scheme?.lowercase()
        require(scheme == "https" || (BuildConfig.DEBUG && scheme == "http")) {
            "A secure HTTPS company server is required."
        }
        require(!uri.host.isNullOrBlank() && uri.userInfo == null && uri.query == null && uri.fragment == null) {
            "Enter a valid company server address."
        }
        val path = uri.path.orEmpty().trimEnd('/')
        require(path.isBlank() || path == "/api/v1") {
            "Enter the company server address, not a page inside the app."
        }
        val port = if (uri.port == -1) "" else ":${uri.port}"
        return "$scheme://${uri.host}$port/api/v1/"
    }
}
