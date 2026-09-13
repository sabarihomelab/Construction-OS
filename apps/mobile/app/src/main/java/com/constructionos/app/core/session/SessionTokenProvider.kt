package com.constructionos.app.core.session

interface SessionTokenProvider {
    fun currentToken(): String?
}
