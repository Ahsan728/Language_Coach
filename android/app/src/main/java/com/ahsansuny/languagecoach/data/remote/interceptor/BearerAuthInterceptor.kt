package com.ahsansuny.languagecoach.data.remote.interceptor

import com.ahsansuny.languagecoach.data.preferences.ActiveSessionStore
import javax.inject.Inject
import javax.inject.Singleton
import okhttp3.Interceptor
import okhttp3.Response

@Singleton
class BearerAuthInterceptor @Inject constructor(
    private val activeSessionStore: ActiveSessionStore,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val builder = chain.request().newBuilder()
        activeSessionStore.currentSession()?.let { session ->
            builder.header("Authorization", session.authorizationHeader())
        }
        return chain.proceed(builder.build())
    }
}
