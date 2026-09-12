package com.constructionos.app.ui

import com.google.gson.JsonArray

fun List<String>.toJsonArray(): String {
    val array = JsonArray()
    forEach { value -> array.add(value) }
    return array.toString()
}
