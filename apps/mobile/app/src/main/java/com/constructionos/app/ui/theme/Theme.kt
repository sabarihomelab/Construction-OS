package com.constructionos.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val LightColors = lightColorScheme(
    primary = Color(0xFFB96100),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFE2BB),
    onPrimaryContainer = Color(0xFF351A00),
    secondary = Color(0xFF315F8C),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFD4E7FF),
    onSecondaryContainer = Color(0xFF071E33),
    tertiary = Color(0xFF217A4A),
    onTertiary = Color.White,
    background = Color(0xFFF3F5F7),
    onBackground = Color(0xFF111417),
    surface = Color(0xFFFCFCFD),
    onSurface = Color(0xFF111417),
    surfaceVariant = Color(0xFFE7EBEF),
    onSurfaceVariant = Color(0xFF555E67),
    outline = Color(0xFFC7CDD3),
    outlineVariant = Color(0xFFDDE2E7),
    error = Color(0xFFB3261E),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFFFB94D),
    onPrimary = Color(0xFF2C1900),
    primaryContainer = Color(0xFF573400),
    onPrimaryContainer = Color(0xFFFFDDAE),
    secondary = Color(0xFF94C8FF),
    onSecondary = Color(0xFF07304F),
    secondaryContainer = Color(0xFF153E60),
    onSecondaryContainer = Color(0xFFD3E9FF),
    tertiary = Color(0xFF67D79A),
    onTertiary = Color(0xFF00391F),
    background = Color(0xFF090B0E),
    onBackground = Color(0xFFF0F2F4),
    surface = Color(0xFF11151A),
    onSurface = Color(0xFFF0F2F4),
    surfaceVariant = Color(0xFF1A2027),
    onSurfaceVariant = Color(0xFFB7C0C9),
    outline = Color(0xFF3A424B),
    outlineVariant = Color(0xFF252C33),
    error = Color(0xFFFFB4AB),
)

private val ConstructionTypography = Typography(
    headlineLarge = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 30.sp,
        lineHeight = 36.sp,
        letterSpacing = (-0.4).sp,
    ),
    headlineMedium = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 26.sp,
        lineHeight = 32.sp,
        letterSpacing = (-0.3).sp,
    ),
    titleLarge = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 21.sp,
        lineHeight = 27.sp,
        letterSpacing = (-0.15).sp,
    ),
    titleMedium = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 17.sp,
        lineHeight = 23.sp,
    ),
    titleSmall = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 15.sp,
        lineHeight = 20.sp,
    ),
    bodyLarge = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 23.sp,
    ),
    bodyMedium = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 20.sp,
    ),
    bodySmall = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 12.5.sp,
        lineHeight = 18.sp,
    ),
    labelLarge = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 13.sp,
        lineHeight = 18.sp,
        letterSpacing = 0.1.sp,
    ),
    labelMedium = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 11.5.sp,
        lineHeight = 16.sp,
        letterSpacing = 0.2.sp,
    ),
)

private val ConstructionShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(26.dp),
    extraLarge = RoundedCornerShape(32.dp),
)

@Composable
fun ConstructionOsTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        typography = ConstructionTypography,
        shapes = ConstructionShapes,
        content = content,
    )
}
