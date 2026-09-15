package com.constructionos.app.core.auth

import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateOf
import com.constructionos.app.core.network.ConstructionOsApi
import com.constructionos.app.core.network.NativeAuthenticationRequest
import com.constructionos.app.core.network.NativeAuthenticationResponse
import com.constructionos.app.core.network.NativeMembershipOption
import com.constructionos.app.core.network.NativeMembershipSelectionRequest
import com.constructionos.app.core.network.SessionContextResponse
import com.constructionos.app.core.session.SecureSessionStore
import retrofit2.HttpException

sealed interface AuthUiState {
    data object Bootstrapping : AuthUiState

    data class SignedOut(
        val providers: List<String>,
        val message: String? = null,
    ) : AuthUiState

    data class MembershipSelection(
        val grantToken: String,
        val memberships: List<NativeMembershipOption>,
    ) : AuthUiState

    data class Authenticated(
        val context: SessionContextResponse,
    ) : AuthUiState

    data class Error(
        val message: String,
    ) : AuthUiState
}

class AuthController(
    private val api: ConstructionOsApi,
    private val sessionStore: SecureSessionStore,
) {
    private val mutableState = mutableStateOf<AuthUiState>(AuthUiState.Bootstrapping)
    val state: State<AuthUiState> = mutableState

    suspend fun restoreSession() {
        mutableState.value = AuthUiState.Bootstrapping
        val token = sessionStore.currentToken()
        if (token.isNullOrBlank()) {
            loadProviders()
            return
        }

        runCatching { api.sessionContext() }
            .onSuccess { mutableState.value = AuthUiState.Authenticated(it) }
            .onFailure { error ->
                if (error is HttpException && error.code() == 401) {
                    sessionStore.clear()
                    loadProviders("Your session expired. Sign in again.")
                } else {
                    mutableState.value = AuthUiState.Error(
                        error.message ?: "Unable to restore your session.",
                    )
                }
            }
    }

    suspend fun loadProviders(message: String? = null) {
        runCatching { api.nativeProviders() }
            .onSuccess {
                mutableState.value = AuthUiState.SignedOut(
                    providers = it.providers,
                    message = message,
                )
            }
            .onFailure {
                mutableState.value = AuthUiState.Error(
                    it.message ?: "Unable to reach Construction OS.",
                )
            }
    }

    suspend fun loginWithDevelopmentProvider(email: String, secret: String) {
        authenticate(
            NativeAuthenticationRequest(
                providerKey = "development",
                payload = mapOf(
                    "email" to email.trim(),
                    "secret" to secret,
                ),
            ),
        )
    }

    suspend fun selectMembership(grantToken: String, membershipId: String) {
        mutableState.value = AuthUiState.Bootstrapping
        runCatching {
            api.selectMembership(
                NativeMembershipSelectionRequest(
                    grantToken = grantToken,
                    membershipId = membershipId,
                ),
            )
        }.onSuccess { completeAuthentication(it) }
            .onFailure { loadProviders(authenticationFailureMessage(it)) }
    }

    suspend fun logout() {
        runCatching { api.logout() }
        sessionStore.clear()
        loadProviders()
    }

    suspend fun retry() {
        if (sessionStore.currentToken().isNullOrBlank()) {
            loadProviders()
        } else {
            restoreSession()
        }
    }

    private suspend fun authenticate(request: NativeAuthenticationRequest) {
        mutableState.value = AuthUiState.Bootstrapping
        runCatching { api.authenticateNative(request) }
            .onSuccess { completeAuthentication(it) }
            .onFailure { loadProviders(authenticationFailureMessage(it)) }
    }

    private suspend fun completeAuthentication(response: NativeAuthenticationResponse) {
        when (response.status) {
            NativeAuthenticationResponse.STATUS_AUTHENTICATED -> {
                val token = response.requireBearerToken()
                sessionStore.save(token)
                runCatching { api.sessionContext() }
                    .onSuccess { mutableState.value = AuthUiState.Authenticated(it) }
                    .onFailure {
                        sessionStore.clear()
                        loadProviders("Signed in, but access context could not be loaded.")
                    }
            }

            NativeAuthenticationResponse.STATUS_MEMBERSHIP_SELECTION -> {
                val grant = response.grantToken
                if (grant.isNullOrBlank() || response.memberships.isEmpty()) {
                    loadProviders("The server returned an invalid membership selection response.")
                } else {
                    mutableState.value = AuthUiState.MembershipSelection(
                        grantToken = grant,
                        memberships = response.memberships,
                    )
                }
            }

            else -> loadProviders("The server returned an unsupported authentication response.")
        }
    }

    private fun authenticationFailureMessage(error: Throwable): String =
        if (error is HttpException && error.code() == 401) {
            "Sign-in failed. Check your details and try again."
        } else {
            error.message ?: "Sign-in failed."
        }
}
