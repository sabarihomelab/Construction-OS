package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp

@Composable
fun CompanyConnectionScreen(
    initialServerAddress: String,
    isConnecting: Boolean,
    error: String?,
    onConnect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var serverAddress by remember(initialServerAddress) {
        mutableStateOf(initialServerAddress)
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            text = "Connect to your company",
            style = MaterialTheme.typography.headlineMedium,
        )
        Text(
            text = "Enter the Construction OS server address provided by your company administrator. The app will verify the deployment before sign-in.",
            modifier = Modifier.padding(top = 8.dp, bottom = 24.dp),
        )

        OutlinedTextField(
            value = serverAddress,
            onValueChange = { serverAddress = it },
            label = { Text("Company server") },
            placeholder = { Text("https://construction.example.com") },
            supportingText = { Text("Production connections must use HTTPS.") },
            singleLine = true,
            enabled = !isConnecting,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            modifier = Modifier.fillMaxWidth(),
        )

        if (error != null) {
            Text(
                text = error,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 12.dp),
            )
        }

        Button(
            onClick = { onConnect(serverAddress) },
            enabled = serverAddress.isNotBlank() && !isConnecting,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 20.dp),
        ) {
            if (isConnecting) {
                CircularProgressIndicator(
                    modifier = Modifier.padding(end = 12.dp),
                    strokeWidth = 2.dp,
                )
                Text("Verifying company…")
            } else {
                Text("Connect")
            }
        }

        if (isConnecting) {
            Text(
                text = "Checking the company deployment and secure API contract…",
                modifier = Modifier
                    .align(Alignment.CenterHorizontally)
                    .padding(top = 12.dp),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
