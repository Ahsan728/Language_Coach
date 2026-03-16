package com.ahsansuny.languagecoach.data.remote.interceptor

import okhttp3.Interceptor
import okhttp3.Response

class RequestMetadataInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request().newBuilder()
            .header("Accept", "application/json")
            .header("X-Client-Platform", "android")
            .header("X-Client-App", "language-coach")
            .build()
        return chain.proceed(request)
    }
}
