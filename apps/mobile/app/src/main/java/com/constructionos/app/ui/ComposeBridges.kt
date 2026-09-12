package com.constructionos.app.ui

import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.vector.ImageVector
import com.google.gson.JsonArray

@Composable
fun NavigationBarItem(
    selected: Boolean,
    onClick: () -> Unit,
    icon: @Composable () -> Unit,
    label: @Composable (() -> Unit)? = null,
    alwaysShowLabel: Boolean = true,
) {
    androidx.compose.material3.NavigationBarItem(
        selected = selected,
        onClick = onClick,
        icon = icon,
        label = label,
        alwaysShowLabel = alwaysShowLabel,
    )
}

fun List<String>.toJsonArray(): String {
    val array = JsonArray()
    forEach(array::add)
    return array.toString()
}
