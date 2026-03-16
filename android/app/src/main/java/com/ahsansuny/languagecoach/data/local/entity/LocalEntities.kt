package com.ahsansuny.languagecoach.data.local.entity

import androidx.room.Entity
import com.ahsansuny.languagecoach.core.model.LanguageCode
import com.ahsansuny.languagecoach.core.model.LanguageProgressSummary
import com.ahsansuny.languagecoach.core.model.LessonProgressSummary
import com.ahsansuny.languagecoach.core.model.LessonSummary
import com.ahsansuny.languagecoach.core.model.ProgressSnapshot
import com.ahsansuny.languagecoach.core.model.VocabularyEntry

@Entity(
    tableName = "lessons",
    primaryKeys = ["languageCode", "remoteId"],
)
data class LessonEntity(
    val languageCode: String,
    val remoteId: Int,
    val icon: String?,
    val titleEn: String,
    val titleBn: String,
    val titleLang: String,
    val descriptionEn: String,
    val descriptionBn: String,
    val tipEn: String,
    val tipBn: String,
    val activity: String?,
    val vocabularyCategoriesRaw: String,
    val hasGrammar: Boolean,
    val progressCompleted: Boolean?,
    val progressBestScore: Int?,
    val progressAttempts: Int?,
    val progressLastSeenIso: String?,
    val cefrLevel: String,
    val updatedAtEpochMs: Long,
)

@Entity(
    tableName = "vocabulary",
    primaryKeys = ["languageCode", "entryKey"],
)
data class VocabularyEntity(
    val languageCode: String,
    val entryKey: String,
    val word: String,
    val article: String?,
    val english: String,
    val bengali: String,
    val pronunciation: String,
    val example: String,
    val exampleEn: String,
    val exampleBn: String,
    val category: String,
    val updatedAtEpochMs: Long,
)

@Entity(tableName = "progress_snapshots")
data class ProgressSnapshotEntity(
    @androidx.room.PrimaryKey val ownerKey: String = SELF_OWNER_KEY,
    val xpToday: Int,
    val reviewsToday: Int,
    val correctToday: Int,
    val wrongToday: Int,
    val streakDays: Int,
    val frenchCompleted: Int,
    val frenchTotal: Int,
    val frenchPercent: Int,
    val frenchRecommendedLessonId: Int?,
    val frenchLastSeenLessonId: Int?,
    val spanishCompleted: Int,
    val spanishTotal: Int,
    val spanishPercent: Int,
    val spanishRecommendedLessonId: Int?,
    val spanishLastSeenLessonId: Int?,
    val updatedAtEpochMs: Long,
) {
    companion object {
        const val SELF_OWNER_KEY = "self"
    }
}

fun LessonEntity.toDomain(): LessonSummary =
    LessonSummary(
        id = remoteId,
        language = LanguageCode.fromApiValue(languageCode),
        cefrLevel = cefrLevel,
        icon = icon,
        titleEn = titleEn,
        titleBn = titleBn,
        titleLang = titleLang,
        descriptionEn = descriptionEn,
        descriptionBn = descriptionBn,
        tipEn = tipEn,
        tipBn = tipBn,
        activity = activity,
        vocabularyCategories = vocabularyCategoriesRaw
            .split('|')
            .filter { it.isNotBlank() },
        hasGrammar = hasGrammar,
        progress = progressCompleted?.let {
            LessonProgressSummary(
                completed = it,
                bestScore = progressBestScore ?: 0,
                attempts = progressAttempts ?: 0,
                lastSeenIso = progressLastSeenIso,
            )
        },
    )

fun VocabularyEntity.toDomain(): VocabularyEntry =
    VocabularyEntry(
        language = LanguageCode.fromApiValue(languageCode),
        word = word,
        article = article,
        english = english,
        bengali = bengali,
        pronunciation = pronunciation,
        example = example,
        exampleEn = exampleEn,
        exampleBn = exampleBn,
        category = category,
    )

fun ProgressSnapshotEntity.toDomain(): ProgressSnapshot =
    ProgressSnapshot(
        xpToday = xpToday,
        reviewsToday = reviewsToday,
        correctToday = correctToday,
        wrongToday = wrongToday,
        streakDays = streakDays,
        totalCompletedLessons = frenchCompleted + spanishCompleted,
        languageSummaries = listOf(
            LanguageProgressSummary(
                language = LanguageCode.FRENCH,
                completed = frenchCompleted,
                total = frenchTotal,
                percent = frenchPercent,
                recommendedLessonId = frenchRecommendedLessonId,
                lastSeenLessonId = frenchLastSeenLessonId,
            ),
            LanguageProgressSummary(
                language = LanguageCode.SPANISH,
                completed = spanishCompleted,
                total = spanishTotal,
                percent = spanishPercent,
                recommendedLessonId = spanishRecommendedLessonId,
                lastSeenLessonId = spanishLastSeenLessonId,
            ),
        ),
    )
