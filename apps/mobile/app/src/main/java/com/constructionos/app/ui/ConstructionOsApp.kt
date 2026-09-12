package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.constructionos.app.BuildConfig
import com.constructionos.app.core.AppContainer
import com.constructionos.app.core.auth.AuthUiState
import com.constructionos.app.core.deployment.WorkspaceConnection
import com.constructionos.app.core.deployment.WorkspaceConnectionService
import com.constructionos.app.core.deployment.WorkspaceConnectionStore
import com.constructionos.app.core.network.NativeMembershipOption
import kotlinx.coroutines.launch

@Composable
fun ConstructionOsApp() {
    val applicationContext = LocalContext.current.applicationContext
    val connectionStore = remember(applicationContext) {
        WorkspaceConnectionStore(applicationContext)
    }
    val connectionService = remember { WorkspaceConnectionService() }
    val scope = rememberCoroutineScope()
    var connection by remember { mutableStateOf(connectionStore.current()) }
    var isConnecting by remember { mutableStateOf(false) }
    var connectionError by remember { mutableStateOf<String?>(null) }

    Scaffold { padding ->
        val currentConnection = connection
        if (currentConnection == null) {
            CompanyConnectionScreen(
                initialServerAddress = if (BuildConfig.DEBUG) BuildConfig.API_BASE_URL else "",
                isConnecting = isConnecting,
                error = connectionError,
                modifier = Modifier.padding(padding),
                onConnect = { serverAddress ->
                    scope.launch {
                        isConnecting = true
                        connectionError = null
                        runCatching { connectionService.connect(serverAddress) }
                            .onSuccess { verified ->
                                connectionStore.save(verified)
                                connection = verified
                            }
                            .onFailure { error ->
                                connectionError = connectionFailureMessage(error)
                            }
                        isConnecting = false
                    }
                },
            )
        } else {
            ConnectedConstructionOsApp(
                connection = currentConnection,
                modifier = Modifier.padding(padding),
                onChangeCompany = {
                    connectionStore.clear()
                    connectionError = null
                    connection = null
                },
            )
        }
    }
}

@Composable
private fun ConnectedConstructionOsApp(
    connection: WorkspaceConnection,
    onChangeCompany: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val applicationContext = LocalContext.current.applicationContext
    val container = remember(
        applicationContext,
        connection.deploymentId,
        connection.apiBaseUrl,
    ) {
        AppContainer(applicationContext, connection)
    }
    val controller = container.authController
    val state by controller.state
    val scope = rememberCoroutineScope()

    LaunchedEffect(controller) {
        controller.restoreSession()
    }

    when (val current = state) {
        AuthUiState.Bootstrapping -> LoadingScreen(modifier = modifier)

        is AuthUiState.SignedOut -> LoginScreen(
            companyName = connection.organizationName,
            environmentName = connection.environmentName,
            providers = current.providers,
            message = current.message,
            modifier = modifier,
            onDevelopmentLogin = { email, secret ->
                scope.launch { controller.loginWithDevelopmentProvider(email, secret) }
            },
            onChangeCompany = onChangeCompany,
        )

        is AuthUiState.MembershipSelection -> MembershipSelectionScreen(
            memberships = current.memberships,
            modifier = modifier,
            onSelect = { membershipId ->
                scope.launch {
                    controller.selectMembership(current.grantToken, membershipId)
                }
            },
        )

        is AuthUiState.Authenticated -> {
            val expectedOrganizationId = connection.organizationId
            if (
                expectedOrganizationId != null &&
                current.context.organizationId != expectedOrganizationId
            ) {
                ErrorScreen(
                    message = "The signed-in company does not match this deployment.",
                    modifier = modifier,
                    onRetry = { scope.launch { controller.retry() } },
                    onChangeCompany = {
                        scope.launch {
                            controller.logout()
                            onChangeCompany()
                        }
                    },
                )
            } else {
                WorkspaceNavigation(
                    context = current.context,
                    workspace = container.workspaceCoordinator,
                    attendanceRepository = container.attendanceRepository,
                    dprRepository = container.dprRepository,
                    partyRepository = container.partyRepository,
                    wbsRepository = container.wbsRepository,
                    boqFieldRepository = container.boqFieldRepository,
                    accessAdminRepository = container.accessAdminRepository,
                    projectAccessAdminRepository = container.projectAccessAdminRepository,
                    modifier = modifier,
                    onLogout = {
                        scope.launch {
                            container.workspaceCoordinator.logout(current.context.organizationId)
                            controller.logout()
                        }
                    },
                )
            }
        }

        is AuthUiState.Error -> ErrorScreen(
            message = current.message,
            modifier = modifier,
            onRetry = { scope.launch { controller.retry() } },
            onChangeCompany = {
                scope.launch {
                    controller.logout()
                    onChangeCompany()
                }
            },
        )
    }
}

private fun connectionFailureMessage(error: Throwable): String =
    when (error) {
        is IllegalArgumentException -> error.message ?: "The company server address is invalid."
        else -> "Unable to verify this Construction OS company server. Check the address and network connection."
    }

@Composable
private fun LoadingScreen(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        CircularProgressIndicator()
        Text(
            text = "Loading Construction OS…",
            modifier = Modifier.padding(top = 16.dp),
        )
    }
}

@Composable
private fun LoginScreen(
    companyName: String,
    environmentName: String,
    providers: List<String>,
    message: String?,
    onDevelopmentLogin: (String, String) -> Unit,
    onChangeCompany: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var email by remember { mutableStateOf("") }
    var secret by remember { mutableStateOf("") }
    val developmentEnabled = "development" in providers

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(companyName, style = MaterialTheme.typography.headlineMedium)
        Text(
            text = "Construction OS · $environmentName",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 4.dp),
        )
        Text(
            "Sign in to load this company's server-authorized workspace.",
            modifier = Modifier.padding(top = 8.dp, bottom = 24.dp),
        )

        if (message != null) {
            Text(
                text = message,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(bottom = 16.dp),
            )
        }

        if (developmentEnabled) {
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                label = { Text("Email") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = secret,
                onValueChange = { secret = it },
                label = { Text("Development secret") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 12.dp),
            )
            Button(
                onClick = { onDevelopmentLogin(email, secret) },
                enabled = email.isNotBlank() && secret.isNotBlank(),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 16.dp),
            ) {
                Text("Sign in")
            }
        } else {
            Text(
                "No interactive native provider is configured for this environment yet.",
                style = MaterialTheme.typography.bodyLarge,
            )
        }

        OutlinedButton(
            onClick = onChangeCompany,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 16.dp),
        ) {
            Text("Change company")
        }
    }
}

@Composable
private fun MembershipSelectionScreen(
    memberships: List<NativeMembershipOption>,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
    ) {
        Text("Choose company access", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Choose the active membership returned by this company deployment.",
            modifier = Modifier.padding(top = 8.dp, bottom = 16.dp),
        )
        LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            items(memberships, key = { it.membershipId }) { membership ->
                OutlinedButton(
                    onClick = { onSelect(membership.membershipId) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(membership.organizationName)
                }
            }
        }
    }
}

@Composable
private fun ErrorScreen(
    message: String,
    onRetry: () -> Unit,
    onChangeCompany: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(message, color = MaterialTheme.colorScheme.error)
        Button(
            onClick = onRetry,
            modifier = Modifier.padding(top = 16.dp),
        ) {
            Text("Retry")
        }
        OutlinedButton(
            onClick = onChangeCompany,
            modifier = Modifier.padding(top = 12.dp),
        ) {
            Text("Change company")
        }
    }
}
