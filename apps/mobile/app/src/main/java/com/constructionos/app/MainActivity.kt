package com.constructionos.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.constructionos.app.ui.ConstructionOsApp
import com.constructionos.app.ui.theme.ConstructionOsTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            ConstructionOsTheme {
                ConstructionOsApp()
            }
        }
    }
}
