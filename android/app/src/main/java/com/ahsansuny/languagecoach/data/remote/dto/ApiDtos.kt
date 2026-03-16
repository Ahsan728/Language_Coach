package com.ahsansuny.languagecoach.data.remote.dto

import com.ahsansuny.languagecoach.core.model.AuthSession
import com.ahsansuny.languagecoach.core.model.AuthenticatedUser
import com.ahsansuny.languagecoach.core.model.LanguageCode
import com.ahsansuny.languagecoach.data.local.entity.LessonEntity
import com.ahsansuny.languagecoach.data.local.entity.ProgressSnapshotEntity
import com.ahsansuny.languagecoach.data.local.entity.VocabularyEntity
import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import java.security.MessageDigest

@JsonClass(generateAdapter = true)
data class CreateSessionRequest(
    val email: String,
    val name: String,
    @Json(name = "remember_me") val rememberMe: Boolean,
)

@JsonClass(generateAdapter = true)
data class UserDto(
    val id: Long,
    val name: String,
    val email: String,
    @Json(name = "created_at") val createdAt: String? = null,
    @Json(name = "last_login") val lastLogin: String? = null,
)

@JsonClass(generateAdapter = true)
data class AuthSessionResponse(
    val ok: Boolean,
    @Json(name = "auth_mode") val authMode: String,
    @Json(name = "access_token") val accessToken: String,
    @Json(name = "token_type") val tokenType: String,
    @Json(name = "expires_at") val expiresAt: String? = null,
    val user: UserDto,
)

@JsonClass(generateAdapter = true)
data class MeResponse(
    val ok: Boolean,
    val user: UserDto,
)

@JsonClass(generateAdapter = true)
data class OkResponse(
    val ok: Boolean,
)

@JsonClass(generateAdapter = true)
data class LanguageDto(
    val id: String,
    val name: String,
    @Json(name = "name_native") val nameNative: String,
    @Json(name = "name_bn") val nameBn: String,
    val flag: String,
    val color: String,
    @Json(name = "lesson_count") val lessonCount: Int,
    @Json(name = "vocabulary_category_count") val vocabularyCategoryCount: Int,
    @Json(name = "vocabulary_word_count") val vocabularyWordCount: Int,
)

@JsonClass(generateAdapter = true)
data class LanguagesResponse(
    val ok: Boolean,
    val languages: List<LanguageDto>,
)

@JsonClass(generateAdapter = true)
data class LessonProgressDto(
    val completed: Boolean,
    @Json(name = "best_score") val bestScore: Int,
    val attempts: Int,
    @Json(name = "last_seen") val lastSeen: String? = null,
)

@JsonClass(generateAdapter = true)
data class LessonSummaryDto(
    val id: Int,
    @Json(name = "cefr_level") val cefrLevel: String,
    val icon: String? = null,
    @Json(name = "title_en") val titleEn: String,
    @Json(name = "title_bn") val titleBn: String,
    @Json(name = "title_lang") val titleLang: String,
    @Json(name = "description_en") val descriptionEn: String,
    @Json(name = "description_bn") val descriptionBn: String,
    @Json(name = "tip_en") val tipEn: String,
    @Json(name = "tip_bn") val tipBn: String,
    val activity: String? = null,
    @Json(name = "vocabulary_categories") val vocabularyCategories: List<String> = emptyList(),
    @Json(name = "has_grammar") val hasGrammar: Boolean = false,
    val progress: LessonProgressDto? = null,
)

@JsonClass(generateAdapter = true)
data class LessonsResponse(
    val ok: Boolean,
    val language: String,
    @Json(name = "recommended_lesson_id") val recommendedLessonId: Int? = null,
    val lessons: List<LessonSummaryDto>,
)

@JsonClass(generateAdapter = true)
data class VocabularyCategoryDto(
    val id: String,
    val label: String,
    val count: Int,
)

@JsonClass(generateAdapter = true)
data class VocabularyItemDto(
    val word: String,
    val article: String? = null,
    val english: String,
    val bengali: String,
    val pronunciation: String,
    val example: String,
    @Json(name = "example_en") val exampleEn: String,
    @Json(name = "example_bn") val exampleBn: String,
    val category: String,
)

@JsonClass(generateAdapter = true)
data class VocabularyResponse(
    val ok: Boolean,
    val language: String,
    val category: String,
    val offset: Int,
    val limit: Int,
    val total: Int,
    val categories: List<VocabularyCategoryDto>,
    val items: List<VocabularyItemDto>,
)

@JsonClass(generateAdapter = true)
data class ProgressTodayDto(
    @Json(name = "xp_today") val xpToday: Int,
    @Json(name = "reviews_today") val reviewsToday: Int,
    @Json(name = "correct_today") val correctToday: Int,
    @Json(name = "wrong_today") val wrongToday: Int,
    @Json(name = "streak_days") val streakDays: Int,
)

@JsonClass(generateAdapter = true)
data class LanguageProgressDto(
    val completed: Int,
    val total: Int,
    val percent: Int,
    @Json(name = "recommended_lesson_id") val recommendedLessonId: Int? = null,
    @Json(name = "last_seen_lesson_id") val lastSeenLessonId: Int? = null,
)

@JsonClass(generateAdapter = true)
data class ProgressResponse(
    val ok: Boolean,
    val today: ProgressTodayDto,
    val languages: Map<String, LanguageProgressDto>,
)

@JsonClass(generateAdapter = true)
data class LessonTouchResponse(
    val ok: Boolean,
    @Json(name = "last_seen") val lastSeen: String,
)

fun UserDto.toDomain(): AuthenticatedUser =
    AuthenticatedUser(
        id = id,
        name = name,
        email = email,
        createdAtIso = createdAt,
        lastLoginIso = lastLogin,
    )

fun AuthSessionResponse.toDomain(): AuthSession =
    AuthSession(
        accessToken = accessToken,
        tokenType = tokenType,
        expiresAtIso = expiresAt,
        authMode = authMode,
        user = user.toDomain(),
    )

fun LessonSummaryDto.toEntity(languageCode: LanguageCode): LessonEntity =
    LessonEntity(
        languageCode = languageCode.apiValue,
        remoteId = id,
        icon = icon,
        titleEn = titleEn,
        titleBn = titleBn,
        titleLang = titleLang,
        descriptionEn = descriptionEn,
        descriptionBn = descriptionBn,
        tipEn = tipEn,
        tipBn = tipBn,
        activity = activity,
        vocabularyCategoriesRaw = vocabularyCategories.joinToString("|"),
        hasGrammar = hasGrammar,
        progressCompleted = progress?.completed,
        progressBestScore = progress?.bestScore,
        progressAttempts = progress?.attempts,
        progressLastSeenIso = progress?.lastSeen,
        cefrLevel = cefrLevel,
        updatedAtEpochMs = System.currentTimeMillis(),
    )

fun VocabularyItemDto.toEntity(languageCode: LanguageCode): VocabularyEntity =
    VocabularyEntity(
        languageCode = languageCode.apiValue,
        entryKey = stableVocabularyEntryKey(languageCode, this),
        word = word,
        article = article,
        english = english,
        bengali = bengali,
        pronunciation = pronunciation,
        example = example,
        exampleEn = exampleEn,
        exampleBn = exampleBn,
        category = category,
        updatedAtEpochMs = System.currentTimeMillis(),
    )

fun stableVocabularyEntryKey(
    languageCode: LanguageCode,
    item: VocabularyItemDto,
): String {
    val rawKey = buildString {
        append(languageCode.apiValue)
        append('\u001f')
        append(item.category)
        append('\u001f')
        append(item.word)
        append('\u001f')
        append(item.article.orEmpty())
        append('\u001f')
        append(item.english)
        append('\u001f')
        append(item.bengali)
        append('\u001f')
        append(item.pronunciation)
        append('\u001f')
        append(item.example)
        append('\u001f')
        append(item.exampleEn)
        append('\u001f')
        append(item.exampleBn)
    }
    val digest = MessageDigest.getInstance("SHA-256").digest(rawKey.toByteArray(Charsets.UTF_8))
    return digest.joinToString(separator = "") { byte -> "%02x".format(byte) }
}

fun ProgressResponse.toEntity(): ProgressSnapshotEntity {
    val french = languages[LanguageCode.FRENCH.apiValue]
    val spanish = languages[LanguageCode.SPANISH.apiValue]
    return ProgressSnapshotEntity(
        xpToday = today.xpToday,
        reviewsToday = today.reviewsToday,
        correctToday = today.correctToday,
        wrongToday = today.wrongToday,
        streakDays = today.streakDays,
        frenchCompleted = french?.completed ?: 0,
        frenchTotal = french?.total ?: 0,
        frenchPercent = french?.percent ?: 0,
        frenchRecommendedLessonId = french?.recommendedLessonId,
        frenchLastSeenLessonId = french?.lastSeenLessonId,
        spanishCompleted = spanish?.completed ?: 0,
        spanishTotal = spanish?.total ?: 0,
        spanishPercent = spanish?.percent ?: 0,
        spanishRecommendedLessonId = spanish?.recommendedLessonId,
        spanishLastSeenLessonId = spanish?.lastSeenLessonId,
        updatedAtEpochMs = System.currentTimeMillis(),
    )
}
