package com.constructionos.app.core.network

import com.constructionos.app.core.session.SessionTokenProvider
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object NetworkFactory {
    fun createApi(
        baseUrl: String,
        tokenProvider: SessionTokenProvider,
    ): ConstructionOsApi = authenticatedRetrofit(baseUrl, tokenProvider)
        .create(ConstructionOsApi::class.java)

    fun createWbsApi(
        baseUrl: String,
        tokenProvider: SessionTokenProvider,
    ): WbsApi = authenticatedRetrofit(baseUrl, tokenProvider)
        .create(WbsApi::class.java)

    fun createBoqFieldApi(
        baseUrl: String,
        tokenProvider: SessionTokenProvider,
    ): BoqFieldApi = authenticatedRetrofit(baseUrl, tokenProvider)
        .create(BoqFieldApi::class.java)

    fun createEstimatingApi(
        baseUrl: String,
        tokenProvider: SessionTokenProvider,
    ): EstimatingApi = authenticatedRetrofit(baseUrl, tokenProvider)
        .create(EstimatingApi::class.java)

    fun createBootstrapApi(baseUrl: String): ConstructionOsApi {
        val client = OkHttpClient.Builder().build()
        return createRetrofit(baseUrl, client).create(ConstructionOsApi::class.java)
    }

    private fun authenticatedRetrofit(
        baseUrl: String,
        tokenProvider: SessionTokenProvider,
    ): Retrofit {
        val client = OkHttpClient.Builder()
            .addInterceptor(BearerSessionInterceptor(tokenProvider))
            .build()
        return createRetrofit(baseUrl, client)
    }

    private fun createRetrofit(baseUrl: String, client: OkHttpClient): Retrofit =
        Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
}
