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
import com.constructionos.app.core.AppContainer
import com.constructionos.app.core.auth.AuthUiState
import com.constructionos.app.core.network.NativeMembershipOption
import kotlinx.coroutines.launch

@Composable
fun ConstructionOsApp() {
    val applicationContext = LocalContext.current.applicationContext
    val container = remember(applicationContext) { AppContainer(applicationContext) }
    val controller = container.authController
    val state by controller.state
    val scope = rememberCoroutineScope()

    LaunchedEffect(controller) {
        controller.restoreSession()
    }

    Scaffold { padding ->
        when (val current = state) {
            AuthUiState.Bootstrapping -> LoadingScreen(
                modifier = Modifier.padding(padding),
            )

            is AuthUiState.SignedOut -> LoginScreen(
                providers = current.providers,
                message = current.message,
                modifier = Modifier.padding(padding),
                onDevelopmentLogin = { email, secret ->
                    scope.launch { controller.loginWithDevelopmentProvider(email, secret) }
                },
            )

            is AuthUiState.MembershipSelection -> MembershipSelectionScreen(
                memberships = current.memberships,
                modifier = Modifier.padding(padding),
                onSelect = { membershipId ->
                    scope.launch {
                        controller.selectMembership(current.grantToken, membershipId)
                    }
                },
            )

            is AuthUiState.Authenticated -> WorkspaceNavigation(
                context = current.context,
                workspace = container.workspaceCoordinator,
                attendanceRepository = container.attendanceRepository,
                dprRepository = container.dprRepository,
                partyRepository = container.partyRepository,
                modifier = Modifier.padding(padding),
                onLogout = {
                    scope.launch {
                        container.workspaceCoordinator.logout(current.context.organizationId)
                        controller.logout()
                    }
                },
            )

            is AuthUiState.Error -> ErrorScreen(
                message = current.message,
                modifier = Modifier.padding(padding),
                onRetry = { scope.launch { controller.retry() } },
            )
        }
    }
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
    providers: List<String>,
    message: String?,
    onDevelopmentLogin: (String, String) -> Unit,
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
        Text("Construction OS", style = MaterialTheme.typography.headlineMedium)
        Text(
            "Sign in to load your server-authorized workspace.",
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
        Text("Choose company", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Your identity belongs to more than one organization.",
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
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Unable to continue", style = MaterialTheme.typography.headlineSmall)
        Text(
            text = message,
            modifier = Modifier.padding(top = 12.dp, bottom = 20.dp),
        )
        Button(onClick = onRetry) {
            Text("Retry")
        }
    }
}
