package com.constructionos.app.ui.design

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

@Composable
fun CosStatusPill(text: String, tone: CosStatusTone) {
    CosStatusPill(text = text, modifier = Modifier, tone = tone)
}
