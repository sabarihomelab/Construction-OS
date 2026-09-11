package com.constructionos.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController

private const val FoundationRoute = "foundation"

@Composable
fun ConstructionOsApp() {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = FoundationRoute,
    ) {
        composable(FoundationRoute) {
            Scaffold { padding ->
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Text(
                        text = "Construction OS",
                        style = MaterialTheme.typography.headlineMedium,
                    )
                    Text(
                        text = "Android foundation ready",
                        style = MaterialTheme.typography.bodyLarge,
                    )
                }
            }
        }
    }
}
