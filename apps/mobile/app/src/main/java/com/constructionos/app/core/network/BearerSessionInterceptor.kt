package com.constructionos.app.core.network

import com.constructionos.app.core.session.SessionTokenProvider
import okhttp3.Interceptor
import okhttp3.Response

class BearerSessionInterceptor(
    private val tokenProvider: SessionTokenProvider,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = tokenProvider.currentToken()
        val request = if (token.isNullOrBlank()) {
            chain.request()
        } else {
            chain.request()
                .newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        }
        return chain.proceed(request)
    }
}
