package com.ahsansuny.languagecoach.core.config

import com.ahsansuny.languagecoach.BuildConfig
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl

enum class EnvironmentFlavor {
    DEV,
    STAGING,
    PROD,
}

data class AppEnvironment(
    val flavor: EnvironmentFlavor,
    val baseUrl: String,
) {
    val baseHttpUrl: HttpUrl = baseUrl.toHttpUrl()
    val baseUrlHost: String = baseHttpUrl.host
}

object RuntimeEnvironment {
    val current: AppEnvironment by lazy {
        AppEnvironment(
            flavor = when (BuildConfig.APP_ENV.lowercase()) {
                "dev" -> EnvironmentFlavor.DEV
                "staging" -> EnvironmentFlavor.STAGING
                else -> EnvironmentFlavor.PROD
            },
            baseUrl = BuildConfig.BASE_URL,
        )
    }
}
