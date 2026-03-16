package com.ahsansuny.languagecoach.core.model

enum class LanguageCode(val apiValue: String, val displayName: String) {
    FRENCH(apiValue = "french", displayName = "French"),
    SPANISH(apiValue = "spanish", displayName = "Spanish");

    companion object {
        fun fromApiValue(value: String): LanguageCode =
            entries.firstOrNull { it.apiValue.equals(value, ignoreCase = true) } ?: FRENCH
    }
}

data class AuthenticatedUser(
    val id: Long,
    val name: String,
    val email: String,
    val createdAtIso: String?,
    val lastLoginIso: String?,
)

data class AuthSession(
    val accessToken: String,
    val tokenType: String,
    val expiresAtIso: String?,
    val authMode: String,
    val user: AuthenticatedUser,
) {
    fun authorizationHeader(): String = "$tokenType $accessToken"
}

data class LessonProgressSummary(
    val completed: Boolean,
    val bestScore: Int,
    val attempts: Int,
    val lastSeenIso: String?,
)

data class LessonSummary(
    val id: Int,
    val language: LanguageCode,
    val cefrLevel: String,
    val icon: String?,
    val titleEn: String,
    val titleBn: String,
    val titleLang: String,
    val descriptionEn: String,
    val descriptionBn: String,
    val tipEn: String,
    val tipBn: String,
    val activity: String?,
    val vocabularyCategories: List<String>,
    val hasGrammar: Boolean,
    val progress: LessonProgressSummary?,
)

data class VocabularyEntry(
    val language: LanguageCode,
    val word: String,
    val article: String?,
    val english: String,
    val bengali: String,
    val pronunciation: String,
    val example: String,
    val exampleEn: String,
    val exampleBn: String,
    val category: String,
)

data class LanguageProgressSummary(
    val language: LanguageCode,
    val completed: Int,
    val total: Int,
    val percent: Int,
    val recommendedLessonId: Int?,
    val lastSeenLessonId: Int?,
)

data class ProgressSnapshot(
    val xpToday: Int,
    val reviewsToday: Int,
    val correctToday: Int,
    val wrongToday: Int,
    val streakDays: Int,
    val totalCompletedLessons: Int,
    val languageSummaries: List<LanguageProgressSummary>,
)
