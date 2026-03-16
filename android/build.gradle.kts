import java.io.File

val sharedBuildRoot: File = System.getenv("LOCALAPPDATA")
    ?.let { File(it, "LanguageCoachAndroidBuild") }
    ?: rootDir.resolve(".gradle-build")

layout.buildDirectory.set(sharedBuildRoot.resolve("root"))

subprojects {
    layout.buildDirectory.set(sharedBuildRoot.resolve(name))
}

plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.ksp) apply false
    alias(libs.plugins.hilt) apply false
}
