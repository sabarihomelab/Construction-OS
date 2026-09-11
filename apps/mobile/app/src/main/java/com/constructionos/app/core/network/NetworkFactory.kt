package com.constructionos.app.core.network

import com.constructionos.app.BuildConfig
import com.constructionos.app.core.session.SessionTokenProvider
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object NetworkFactory {
    fun createApi(tokenProvider: SessionTokenProvider): ConstructionOsApi {
        val client = OkHttpClient.Builder()
            .addInterceptor(BearerSessionInterceptor(tokenProvider))
            .build()

        return Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ConstructionOsApi::class.java)
    }
}
