package com.constructionos.app.core

import android.content.Context
import com.constructionos.app.core.auth.AuthController
import com.constructionos.app.core.network.NetworkFactory
import com.constructionos.app.core.session.SecureSessionStore

class AppContainer(context: Context) {
    private val sessionStore = SecureSessionStore(context)
    private val api = NetworkFactory.createApi(sessionStore)

    val authController = AuthController(
        api = api,
        sessionStore = sessionStore,
    )
}
