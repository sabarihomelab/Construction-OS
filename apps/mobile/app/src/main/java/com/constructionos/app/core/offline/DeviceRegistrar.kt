package com.constructionos.app.core.offline

import android.content.Context
import android.os.Build
import com.constructionos.app.BuildConfig
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.DeviceRegistrationRequest
import java.util.UUID

class DeviceRegistrar(
    context: Context,
    private val api: ConstructionOsApi,
) {
    private val preferences = context.getSharedPreferences(
        "construction-os-device",
        Context.MODE_PRIVATE,
    )

    suspend fun register(): String {
        val installationId = preferences.getString(KEY_INSTALLATION_ID, null)
            ?: UUID.randomUUID().toString().also { generated ->
                preferences.edit().putString(KEY_INSTALLATION_ID, generated).apply()
            }

        val label = listOf(Build.MANUFACTURER, Build.MODEL)
            .filter { it.isNotBlank() }
            .joinToString(" ")
            .ifBlank { null }

        val device = api.registerDevice(
            DeviceRegistrationRequest(
                installationId = installationId,
                deviceLabel = label,
                appVersion = BuildConfig.VERSION_NAME,
            ),
        )
        preferences.edit().putString(KEY_DEVICE_ID, device.id).apply()
        return device.id
    }

    fun registeredDeviceId(): String? = preferences.getString(KEY_DEVICE_ID, null)

    companion object {
        private const val KEY_INSTALLATION_ID = "installation-id"
        private const val KEY_DEVICE_ID = "device-id"
    }
}
