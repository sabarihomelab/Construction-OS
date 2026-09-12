package com.constructionos.app.core.network

import com.constructionos.app.core.session.SessionTokenProvider
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object NetworkFactory {
    fun createApi(
        baseUrl: String,
        tokenProvider: SessionTokenProvider,
    ): ConstructionOsApi {
        val client = OkHttpClient.Builder()
            .addInterceptor(BearerSessionInterceptor(tokenProvider))
            .build()
        return createRetrofit(baseUrl, client).create(ConstructionOsApi::class.java)
    }

    fun createBootstrapApi(baseUrl: String): ConstructionOsApi {
        val client = OkHttpClient.Builder().build()
        return createRetrofit(baseUrl, client).create(ConstructionOsApi::class.java)
    }

    private fun createRetrofit(baseUrl: String, client: OkHttpClient): Retrofit =
        Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
}
