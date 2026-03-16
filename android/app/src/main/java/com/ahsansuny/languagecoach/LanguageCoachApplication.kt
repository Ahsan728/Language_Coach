package com.ahsansuny.languagecoach

import android.app.Application
import com.ahsansuny.languagecoach.core.config.RuntimeEnvironment
import dagger.hilt.android.HiltAndroidApp
import timber.log.Timber

@HiltAndroidApp
class LanguageCoachApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        if (BuildConfig.ENABLE_VERBOSE_LOGGING) {
            Timber.plant(Timber.DebugTree())
        }
        Timber.i(
            "Language Coach starting in %s with base URL %s",
            RuntimeEnvironment.current.flavor.name,
            RuntimeEnvironment.current.baseUrl,
        )
    }
}
